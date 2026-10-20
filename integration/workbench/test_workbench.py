from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

import install
import workbench


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'; self.source.mkdir()
        self.destination = self.root / 'installed'
        self.checkpoint = self.root / 'checkpoint.json'
        self.checkpoint.write_text(json.dumps({'active': False, 'phase': 'single_probe_hardware_blocked'}))
        self.make_release('first')

    def make_release(self, value):
        (self.source / 'workbench.py').write_text(value)
        files = {'workbench.py': hashlib.sha256(value.encode()).hexdigest()}
        version = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
        (self.source / 'manifest.json').write_text(json.dumps({'version': version, 'files': files}))

    def test_update_preserves_old_release_checkpoint_and_backup(self):
        original = self.checkpoint.read_bytes()
        first = install.install(self.source, self.destination, self.checkpoint)
        pointer = (self.destination / 'current.json').read_bytes()
        self.make_release('second')
        second = install.install(self.source, self.destination, self.checkpoint)
        self.assertNotEqual(first['release'], second['release'])
        self.assertEqual((Path(first['release']) / 'workbench.py').read_text(), 'first')
        self.assertEqual(self.checkpoint.read_bytes(), original)
        self.assertIn(pointer, [f.read_bytes() for f in self.destination.glob('previous-*.json')])

    def test_corrupt_source_does_not_change_current(self):
        install.install(self.source, self.destination, self.checkpoint)
        before = (self.destination / 'current.json').read_bytes()
        (self.source / 'workbench.py').write_text('tampered')
        with self.assertRaises(RuntimeError):
            install.install(self.source, self.destination, self.checkpoint)
        self.assertEqual((self.destination / 'current.json').read_bytes(), before)

    def test_active_paused_or_cooling_checkpoint_rejected(self):
        for extra in ({'active': True}, {'user_pause': {'active': True}},
                      {'cooling_only': True}, {'migration_hold': {'active': True}}):
            self.checkpoint.write_text(json.dumps({'active': False, **extra}))
            with self.subTest(extra=extra), self.assertRaises(RuntimeError):
                install.install(self.source, self.destination, self.checkpoint)
        self.assertFalse(self.destination.exists())

    def test_checkpoint_change_during_copy_never_activates(self):
        original = install.verify_release
        def changing(folder):
            result = original(folder)
            if folder != self.source:
                self.checkpoint.write_text('{"active": true}')
            return result
        with patch.object(install, 'verify_release', side_effect=changing), self.assertRaises(RuntimeError):
            install.install(self.source, self.destination, self.checkpoint)
        self.assertFalse((self.destination / 'current.json').exists())

    def test_symlink_destination_cannot_redirect_install(self):
        outside = self.root / 'outside'; outside.mkdir()
        self.destination.symlink_to(outside)
        with self.assertRaises(ValueError):
            install.install(self.source, self.destination, self.checkpoint)
        self.assertEqual(list(outside.iterdir()), [])

    def test_missing_or_changed_file_and_path_escape_rejected(self):
        files = {'../outside.py': '0' * 64}
        (self.source / 'manifest.json').write_text(json.dumps({
            'version': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16],
            'files': files}))
        with self.assertRaises(RuntimeError):
            workbench.verify_release(self.source)

    def test_inactive_checkpoint_never_authorizes_probe(self):
        plan = {'boot_id': 'boot', 'reviewed': True}
        base = {'active': True, 'phase': 'reviewed_single_probe_ready',
                'boot_id': 'boot', 'reviewed_presence_plan': plan}
        self.assertTrue(workbench.probe_authorized(base, plan))
        for extra in ({'active': False}, {'phase': 'single_probe_hardware_blocked'},
                      {'boot_id': 'old'}, {'reviewed_presence_plan': {}},
                      {'user_pause': {'active': True}}, {'cooling_only': True}):
            with self.subTest(extra=extra):
                self.assertFalse(workbench.probe_authorized({**base, **extra}, plan))

    def test_sensor_result_is_preferred_and_marked_historical(self):
        work = self.root / 'work';work.mkdir()
        result = work / 'sensor-result.json'
        result.write_text(json.dumps({'passed': True, 'shutdown_verified': True,
                                    'trial': {'received_frames': 120}}))
        with patch.object(workbench, 'PROJECT', self.root):
            r = workbench.last_trial({'latest_sensor_only_result': str(result)})
        self.assertTrue(r['historical_only'])
        self.assertTrue(r['shutdown_verified'])
        self.assertEqual(r['received_frames'], 120)

    def test_sensor_result_outside_project_is_not_read(self):
        result = self.root / 'outside.json';result.write_text('invalid')
        with patch.object(workbench, 'PROJECT', self.root):
            r = workbench.last_trial({'latest_sensor_only_result': str(result)})
        self.assertFalse(r['available'])

    def test_latest_trial_uses_event_time_not_trial_type(self):
        work=self.root/'work';work.mkdir()
        sensor=work/'sensor.json';face=work/'face.json'
        sensor.write_text(json.dumps({'trial': {'started':'2026-10-13T20:00:00+02:00', 'received_frames':120}}))
        face.write_text(json.dumps({'started':'2026-10-13T21:26:00+02:00','counted_session':{'saved_frames':87}}))
        state={'latest_sensor_only_result':str(sensor),'latest_face_result':str(face)}
        with patch.object(workbench,'PROJECT',self.root):
            r=workbench.last_trial(state)
            self.assertEqual(r['kind'],'face_capture')
            self.assertEqual(r['saved_frames'],87)
            self.assertFalse(r['quality_validated'])
            sensor.write_text(json.dumps({'trial': {'started':'2026-10-13T22:00:00+02:00'}}))
            self.assertEqual(workbench.last_trial(state)['kind'],'sensor_only')
            sensor.write_text(json.dumps({'trial': {}}))
            self.assertFalse(workbench.last_trial(state)['available'])

    def test_local_describe_has_no_hardware_side_effects(self):
        with patch.object(workbench, 'ensure_host', side_effect=AssertionError('hardware access')), \
                patch('sys.argv', ['workbench.py', 'describe']):
            self.assertEqual(workbench.main(), 0)


if __name__ == '__main__':
    unittest.main()
