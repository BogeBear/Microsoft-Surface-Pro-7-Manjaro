import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('reboot_guard', Path(__file__).with_name('reboot_guard.py'))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class RebootGuardTests(unittest.TestCase):
    def setup_tree(self, folder, value='48000'):
        root = Path(folder) / 'hwmon4'
        root.mkdir()
        (root / 'name').write_text('coretemp\n')
        for i, label in enumerate(sorted(guard.REQUIRED_LABELS), 1):
            (root / f'temp{i}_label').write_text(label)
            (root / f'temp{i}_input').write_text(value)
        return root

    def test_cpu_labels_and_units(self):
        with tempfile.TemporaryDirectory() as folder:
            self.setup_tree(folder)
            value = guard.read_cpu(Path(folder))
            self.assertEqual(value['maximum_c'], 48)
            self.assertTrue(value['below_limit'])

    def test_hottest_core_not_only_package_controls_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.setup_tree(folder)
            (root / 'temp1_input').write_text('60000')
            self.assertFalse(guard.read_cpu(Path(folder))['below_limit'])

    def test_all_package_and_core_boundaries_are_strictly_below_60(self):
        for value, expected in [('59999', True), ('60000', False), ('60001', False)]:
            for index in range(1, 6):
                with self.subTest(value=value, sensor=index), tempfile.TemporaryDirectory() as folder:
                    root = self.setup_tree(folder)
                    (root / f'temp{index}_input').write_text(value)
                    self.assertEqual(guard.read_cpu(Path(folder))['below_limit'], expected)

    def test_missing_sensor_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.setup_tree(folder)
            (root / 'temp1_input').unlink()
            with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                guard.read_cpu(Path(folder))

    def test_unreadable_value_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.setup_tree(folder)
            (root / 'temp1_input').write_text('invalid')
            with self.assertRaises(ValueError):
                guard.read_cpu(Path(folder))

    def test_alarm_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.setup_tree(folder)
            (root / 'temp1_crit_alarm').write_text('1')
            with self.assertRaisesRegex(RuntimeError, 'alarm'):
                guard.read_cpu(Path(folder))

    def test_temperature_rise_waits_and_requires_three_new_cool_readings(self):
        values = iter([{'below_limit': True}, {'below_limit': False},
                       {'below_limit': True}, {'below_limit': True}, {'below_limit': True}])
        sleeps = []
        result = guard.cool_samples(reader=lambda: next(values), sleeper=sleeps.append)
        self.assertEqual(len(result), 3)
        self.assertEqual(sleeps, [5, 300, 5, 5])

    def test_all_three_readings_required(self):
        sleeps = []
        values = guard.cool_samples(reader=lambda: {'below_limit': True}, sleeper=sleeps.append)
        self.assertEqual(len(values), 3)
        self.assertEqual(sleeps, [5, 5])

    def test_last_moment_rise_cools_before_reboot_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'outputs').mkdir()
            state = base / 'state.json'
            state.write_text(json.dumps({'reboots_authorized': True, 'pending_reboot': {
                'from_boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'reason': 'test', 'requested': False,
                'after_phase': 'camera_recovery_awaiting_postboot_verification',
                'after_next_step': 'Verify new boot, preserve camera block and user absence.'}}))
            saved = []
            with patch.object(guard, 'BASE', base), patch.object(guard, 'STATE', state), \
                 patch('sys.argv', ['guard', '--reboot']), \
                 patch.object(guard, 'cool_samples', return_value=[{'below_limit': True}] * 3) as cooling, \
                 patch.object(guard.time, 'sleep') as waiting, \
                 patch.object(guard, 'read_cpu', side_effect=[{'below_limit': False, 'maximum_c': 61},
                                                            {'below_limit': True, 'maximum_c': 59}]), \
                 patch.object(guard, 'save_state', side_effect=lambda s: saved.append(json.loads(json.dumps(s)))), \
                 patch.object(guard.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as reboot:
                guard.main()
            self.assertEqual(cooling.call_count, 2)
            waiting.assert_called_once_with(300)
            reboot.assert_called_once()
            self.assertEqual(saved[1]['phase'], 'reboot_waiting_for_cpu_cooling')
            self.assertFalse(saved[1]['pending_reboot']['requested'])
            self.assertTrue(saved[-1]['pending_reboot']['requested'])
            self.assertTrue(saved[-1]['pending_reboot']['command_attempted'])
            self.assertEqual(saved[-1]['phase'], 'camera_recovery_awaiting_postboot_verification')
            self.assertEqual(saved[-1]['next_step'], 'Verify new boot, preserve camera block and user absence.')
            self.assertNotIn('login_setup_reboot_started', saved[-1])

    def test_failed_temperature_read_never_calls_reboot(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'outputs').mkdir()
            state = base / 'state.json'
            state.write_text(json.dumps({'reboots_authorized': True, 'pending_reboot': {
                'from_boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'reason': 'test', 'requested': False,
                'after_phase': 'camera_recovery_awaiting_postboot_verification',
                'after_next_step': 'Verify new boot, preserve camera block and user absence.'}}))
            with patch.object(guard, 'BASE', base), patch.object(guard, 'STATE', state), \
                 patch('sys.argv', ['guard', '--reboot']), \
                 patch.object(guard, 'cool_samples', side_effect=OSError('Sensor unavailable')), \
                 patch.object(guard.subprocess, 'run') as reboot, \
                 self.assertRaises(OSError):
                guard.main()
            reboot.assert_not_called()
            self.assertFalse(json.loads(state.read_text())['pending_reboot']['requested'])

    def test_failed_command_keeps_loop_block_and_camera_constraints(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'outputs').mkdir()
            state = base / 'state.json'
            state.write_text(json.dumps({'reboots_authorized': True,
                'hardware_tests_blocked_until_recovery': True,
                'camera_work_paused_by_user': False, 'user_presence': 'absent',
                'pending_reboot': {
                    'from_boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    'reason': 'test', 'requested': False, 'after_phase': 'camera_verification',
                    'after_next_step': 'Verify recovery without starting camera.'}}))
            with patch.object(guard, 'BASE', base), patch.object(guard, 'STATE', state), \
                 patch('sys.argv', ['guard', '--reboot']), \
                 patch.object(guard, 'cool_samples', return_value=[{'below_limit': True}] * 3), \
                 patch.object(guard, 'read_cpu', return_value={'below_limit': True, 'maximum_c': 59}), \
                 patch.object(guard.subprocess, 'run', side_effect=TimeoutError('test command timeout')) as reboot:
                with self.assertRaises(TimeoutError):
                    guard.main()
                with self.assertRaisesRegex(RuntimeError, 'do not repeat'):
                    guard.main()
            reboot.assert_called_once()
            saved = json.loads(state.read_text())
            self.assertTrue(saved['pending_reboot']['requested'])
            self.assertTrue(saved['pending_reboot']['command_attempted'])
            self.assertTrue(saved['hardware_tests_blocked_until_recovery'])
            self.assertFalse(saved['camera_work_paused_by_user'])
            self.assertEqual(saved['user_presence'], 'absent')

    def test_migration_hold_blocks_before_any_temperature_or_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'state.json'
            state.write_text(json.dumps({'reboots_authorized': True, 'migration_hold': {'active': True}}))
            with patch.object(guard, 'STATE', state), patch('sys.argv', ['guard', '--reboot']), \
                 patch.object(guard, 'cool_samples') as cooling, \
                 patch.object(guard.subprocess, 'run') as reboot, \
                 self.assertRaisesRegex(RuntimeError, 'hold'):
                guard.main()
            cooling.assert_not_called()
            reboot.assert_not_called()

    def test_revocation_while_cooling_is_preserved_and_blocks_reboot(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); (base / 'outputs').mkdir()
            state = base / 'state.json'
            data = {'reboots_authorized': True, 'pending_reboot': {
                'from_boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'reason': 'test', 'requested': False,
                'after_phase': 'verification', 'after_next_step': 'Verify only.'}}
            state.write_text(json.dumps(data))
            def revoke():
                data['reboots_authorized'] = False
                data['migration_hold'] = {'active': True}
                state.write_text(json.dumps(data))
                return [{'below_limit': True}] * 3
            with patch.object(guard, 'BASE', base), patch.object(guard, 'STATE', state), \
                 patch('sys.argv', ['guard', '--reboot']), \
                 patch.object(guard, 'cool_samples', side_effect=revoke), \
                 patch.object(guard.subprocess, 'run') as reboot, \
                 self.assertRaisesRegex(RuntimeError, 'hold'):
                guard.main()
            reboot.assert_not_called()
            self.assertEqual(json.loads(state.read_text()), data)

    def test_plan_changed_while_waiting_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'state.json'
            old = {'reboots_authorized': True, 'pending_reboot': {'reason': 'old'}}
            changed = {'reboots_authorized': True, 'pending_reboot': {'reason': 'new'}}
            state.write_text(json.dumps(changed))
            with patch.object(guard, 'STATE', state), self.assertRaisesRegex(RuntimeError, 'plan changed'):
                guard.refresh_authorization(old)
            self.assertEqual(json.loads(state.read_text()), changed)

    def test_missing_postboot_plan_blocks_before_temperature_or_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'state.json'
            state.write_text(json.dumps({'reboots_authorized': True, 'pending_reboot': {
                'from_boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'reason': 'test', 'requested': False}}))
            with patch.object(guard, 'STATE', state), patch('sys.argv', ['guard', '--reboot']), \
                 patch.object(guard, 'cool_samples') as cooling, \
                 patch.object(guard.subprocess, 'run') as reboot, \
                 self.assertRaisesRegex(RuntimeError, 'postboot phase'):
                guard.main()
            cooling.assert_not_called()
            reboot.assert_not_called()


if __name__ == '__main__':
    unittest.main()
