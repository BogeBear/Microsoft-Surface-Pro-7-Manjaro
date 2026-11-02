# SPDX-License-Identifier: GPL-3.0-only
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import sp7_setup as s


def package(version='0.1.0', value=b'first', extra=None):
    files = {'app/example.txt': (value, 0o644)}
    if extra:
        files.update(extra)
    m = {'format': 1, 'version': version, 'profile': 'inactive-workbench',
         'compatibility': {'distribution': 'manjaro', 'arch': 'x86_64',
                           'product': 'Surface Pro 7', 'kernel': s.KERNEL, 'python_min': [3, 11], 'glibc_min': [2, 38]},
         'activation': dict(camera=False, drivers=False, login=False, autostart=False),
         'files': {k: {'sha256': s.digest(v[0]), 'mode': v[1]} for k, v in files.items()}}
    files['manifest.json'] = (s.encode(m), 0o644)
    return s.archive_bytes(files)


class Setup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in {'usr/lib/os-release': 'ID=manjaro\n',
                            'sys/devices/virtual/dmi/id/product_name': 'Surface Pro 7',
                            'sys/devices/virtual/dmi/id/sys_vendor': 'Microsoft Corporation',
                            'proc/sys/kernel/osrelease': s.KERNEL}.items():
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(value)
        self.manager = s.Installer(self.root)
        # Unit-only injection. VM integration below uses a real separate tmpfs mount.
        self.check = mock.patch.object(self.manager, 'check_backup')
        self.check.start()
        self.addCleanup(self.check.stop)
        self.first, self.second = package(), package('0.2.0', b'second')

    def install(self, raw=None):
        raw = self.first if raw is None else raw
        return self.manager.transact(raw, s.digest(raw))

    def active(self):
        return self.manager.current()['manifest']['version']

    def test_install_upgrade_uninstall_and_restore(self):
        self.install()
        r = self.install(self.second)
        self.assertEqual(self.active(), '0.2.0')
        self.assertEqual(len(list((self.manager.base / 'releases').iterdir())), 1)
        self.manager.rollback(r['transaction'])
        self.assertEqual(self.active(), '0.1.0')
        r = self.manager.transact()
        self.assertIsNone(self.manager.current())
        self.manager.rollback(r['transaction'])
        self.assertEqual(self.active(), '0.1.0')

    def test_rollback_first_install_removes_current(self):
        r = self.install()
        self.manager.rollback(r['transaction'])
        self.assertIsNone(self.manager.current())

    def test_idempotent_install(self):
        self.install()
        self.assertEqual(self.install()['status'], 'already-installed')

    def test_deterministic_archive(self):
        self.assertEqual(self.first, package())

    def test_wrong_hash_no_write(self):
        with self.assertRaises(s.Refused):
            self.manager.transact(self.first, '0' * 64)
        self.assertFalse(self.manager.base.exists())

    def test_wrong_versions_fail_before_write(self):
        for name, data in [('usr/lib/os-release', 'ID=arch\n'),
                           ('sys/devices/virtual/dmi/id/product_name', 'Surface Pro 7+'),
                           ('sys/devices/virtual/dmi/id/sys_vendor', 'Other'),
                           ('proc/sys/kernel/osrelease', '7.2.12-surface')]:
            with self.subTest(name=name):
                p = self.root / name
                before = p.read_bytes()
                p.write_text(data)
                with self.assertRaises(s.Refused):
                    self.install()
                self.assertFalse(self.manager.base.exists())
                p.write_bytes(before)

    def test_missing_metadata_refuses(self):
        (self.root / 'proc/sys/kernel/osrelease').unlink()
        with self.assertRaises(OSError):
            self.install()

    def test_metadata_read_requests_remain_small(self):
        original = os.fdopen
        def bounded(fd, mode):
            stream = original(fd, mode)
            class Handle:
                def __enter__(self):return self
                def __exit__(self,*args):stream.close()
                def fileno(self):return stream.fileno()
                def read(self,count):
                    if count > 4096:raise OSError(12,'kernfs allocation too large')
                    return stream.read(count)
            return Handle()
        with mock.patch.object(os,'fdopen',side_effect=bounded):
            self.assertTrue(self.manager.compatibility()['passed'])

    def test_old_libc_and_wrong_arch_refused(self):
        with mock.patch.object(os, 'confstr', return_value='glibc 2.37'):
            self.assertFalse(self.manager.compatibility()['passed'])
        with mock.patch.object(os, 'uname', return_value=type('Info', (), {'machine': 'aarch64'})()):
            self.assertFalse(self.manager.compatibility()['passed'])

    def test_normal_downgrade_and_changed_same_version_refused(self):
        self.install(self.second)
        for raw in [self.first, package('0.2.0', b'different same version')]:
            with self.assertRaises(s.Refused):
                self.install(raw)
        self.assertEqual(self.active(), '0.2.0')

    def test_faults_restore_previous_and_preserve_backup(self):
        self.install()
        for phase in ['backup_saved', 'staged', 'before_switch', 'after_switch']:
            with self.subTest(phase=phase):
                def fail(p):
                    if p == phase:
                        raise OSError('injected disk error')
                self.manager.event = fail
                with self.assertRaises(OSError):
                    self.install(self.second)
                self.assertEqual(self.active(), '0.1.0')
                self.assertTrue(list(self.manager.backup.glob('*/before.tar.gz')))
        self.manager.event = lambda p: None
        self.install(self.second)

    def test_power_loss_after_switch_recover_from_snapshot(self):
        self.install()
        def power_loss(p):
            if p == 'after_switch':
                raise KeyboardInterrupt()
        self.manager.event = power_loss
        with self.assertRaises(KeyboardInterrupt):
            self.install(self.second)
        self.assertEqual(self.active(), '0.2.0')
        tx = next(p for p in self.manager.backup.iterdir()
                  if json.loads((p / 'transaction.json').read_text())['phase'] == 'staged')
        self.manager.event = lambda p: None
        self.manager.rollback(tx.name)
        self.assertEqual(self.active(), '0.1.0')

    def test_uninstall_does_not_require_old_kernel(self):
        self.install()
        (self.root / 'proc/sys/kernel/osrelease').write_text('newer-kernel')
        self.manager.transact()
        self.assertIsNone(self.manager.current())

    def test_changed_file_blocks_uninstall_preserves_it(self):
        self.install()
        folder = self.manager.base / self.manager.current()['release']
        (folder / 'app/example.txt').write_bytes(b'local edits')
        with self.assertRaises(s.Refused):
            self.manager.transact()
        self.assertEqual((folder / 'app/example.txt').read_bytes(), b'local edits')

    def test_unknown_file_blocks_upgrade(self):
        self.install()
        folder = self.manager.base / self.manager.current()['release']
        (folder / 'unknown').write_text('preserve me')
        with self.assertRaises(s.Refused):
            self.install(self.second)

    def test_unknown_empty_directory_is_preserved(self):
        self.install()
        folder = self.manager.base / self.manager.current()['release']
        (folder / 'user-directory').mkdir()
        with self.assertRaises(s.Refused):
            self.manager.transact()
        self.assertTrue((folder / 'user-directory').is_dir())

    def test_changed_mode_blocks_uninstall(self):
        self.install()
        folder = self.manager.base / self.manager.current()['release']
        (folder / 'app/example.txt').chmod(0o666)
        with self.assertRaises(s.Refused):
            self.manager.transact()

    def test_target_symlink_refused(self):
        elsewhere = self.root / 'elsewhere'
        elsewhere.mkdir()
        (self.root / 'opt').symlink_to(elsewhere)
        with self.assertRaises(s.Refused):
            self.install()
        self.assertFalse(list(elsewhere.iterdir()))

    def test_current_link_escape_refused(self):
        self.install()
        (self.manager.base / 'current').unlink()
        (self.manager.base / 'current').symlink_to('/etc')
        with self.assertRaises(s.Refused):
            self.manager.transact()

    def test_backup_symlink_refused(self):
        p = self.manager.backup.parent
        p.mkdir(parents=True)
        self.manager.backup.symlink_to(self.root / 'usr')
        with self.assertRaises(s.Refused):
            self.install()

    def test_same_filesystem_backup_refused(self):
        self.check.stop()
        with self.assertRaises(s.Refused):
            self.install()
        self.assertIsNone(self.manager.current())

    def test_lock_contention(self):
        with self.manager.locked():
            with self.assertRaises(s.Refused):
                self.install()

    def test_lock_symlink_refused(self):
        self.manager.base.mkdir(parents=True)
        (self.manager.base / '.lock').symlink_to(self.root / 'usr/lib/os-release')
        with self.assertRaises(OSError):
            self.install()

    def test_application_lease_blocks_update(self):
        self.install()
        lease = self.manager.use_lease()
        try:
            with self.assertRaises(s.Refused):
                self.install(self.second)
        finally:
            os.close(lease)
        self.install(self.second)

    def test_real_nonroot_read_and_lease(self):
        if os.geteuid() != 0:
            self.skipTest('Actual UID transition is performed in the root VM')
        self.install()
        self.root.chmod(0o755)
        child = os.fork()
        if child == 0:
            try:
                os.setgroups([])
                os.setgid(1000)
                os.setuid(1000)
                self.assertEqual(self.active(), '0.1.0')
                fd = self.manager.use_lease()
                os.close(fd)
                os._exit(0)
            except BaseException:
                os._exit(1)
        _, status = os.waitpid(child, 0)
        self.assertEqual(os.waitstatus_to_exitcode(status), 0)

    def test_restrictive_umask_preserves_public_read_modes(self):
        before = os.umask(0o077)
        try:
            self.install()
        finally:
            os.umask(before)
        folder = self.manager.base / self.manager.current()['release']
        self.assertEqual(stat.S_IMODE(folder.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((self.manager.base / '.lock').stat().st_mode), 0o644)

    def test_staging_write_failure_preserves_active_and_allows_retry(self):
        self.install()
        original = self.manager.write_new
        def fail(path, data, mode=0o600):
            if '.staging-' in str(path) and path.name == 'example.txt':
                raise OSError('injected storage failure')
            return original(path, data, mode)
        with mock.patch.object(self.manager, 'write_new', side_effect=fail):
            with self.assertRaises(OSError):
                self.install(self.second)
        self.assertEqual(self.active(), '0.1.0')
        self.assertFalse(list((self.manager.base / 'releases').glob('.staging-*')))
        self.install(self.second)

    def test_conflicting_paths_refused_before_staging(self):
        raw = package(extra={'app/example.txt/child': (b'bad', 0o644)})
        with self.assertRaises(s.Refused):
            self.install(raw)
        self.assertFalse(self.manager.base.exists())

    def test_rollback_refuses_later_release(self):
        self.install()
        r = self.install(self.second)
        self.install(package('0.3.0', b'third'))
        with self.assertRaises(s.Refused):
            self.manager.rollback(r['transaction'])

    def test_corrupt_backup_refused(self):
        self.install()
        r = self.install(self.second)
        (self.manager.backup / r['transaction'] / 'before.tar.gz').write_bytes(b'corrupt')
        with self.assertRaises(s.Refused):
            self.manager.rollback(r['transaction'])
        self.assertEqual(self.active(), '0.2.0')

    def test_transaction_id_escape_refused(self):
        for tx in ['../x', '/etc', '', 'a' * 31, 'A' * 32]:
            with self.assertRaises(s.Refused):
                self.manager.rollback(tx)

    def test_package_path_and_permission_rejections(self):
        for name in ['../outside', '/absolute', '.', 'app/../bad', 'app//bad', 'app\\bad']:
            with self.subTest(name=name), self.assertRaises(s.Refused):
                s.relative(name)
        for mode in [0o777, 0o4755, 0o600]:
            raw = package(extra={'app/bad': (b'x', mode)})
            with self.assertRaises(s.Refused):
                s.load_package(raw, s.digest(raw))

    def test_missing_extra_or_mismatched_manifest(self):
        m, files = s.load_package(self.first, s.digest(self.first))
        for kind in ['changed', 'missing', 'extra', 'active', 'wrong-profile']:
            edit = dict(files)
            if kind == 'changed':
                edit['app/example.txt'] = (b'changed', 0o644)
            elif kind == 'missing':
                del edit['app/example.txt']
            elif kind == 'extra':
                edit['app/extra'] = (b'new', 0o644)
            else:
                mm = json.loads(files['manifest.json'][0])
                if kind == 'active':
                    mm['activation']['camera'] = True
                else:
                    mm['profile'] = 'drivers'
                edit['manifest.json'] = (s.encode(mm), 0o644)
            raw = s.archive_bytes(edit)
            with self.subTest(kind=kind), self.assertRaises(s.Refused):
                s.load_package(raw, s.digest(raw))

    def test_symlink_hardlink_and_special_archive_entries(self):
        for type_ in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE]:
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w:gz') as t:
                item = tarfile.TarInfo('app/bad')
                item.type, item.linkname, item.mode = type_, '/etc/passwd', 0o644
                t.addfile(item)
            raw = stream.getvalue()
            with self.subTest(type=type_), self.assertRaises(s.Refused):
                s.load_package(raw, s.digest(raw))

    def test_duplicate_tar_entries_refused(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as t:
            for _ in range(2):
                item = tarfile.TarInfo('app/file')
                item.mode = 0o644
                t.addfile(item, io.BytesIO())
        raw = stream.getvalue()
        with self.assertRaises(s.Refused):
            s.load_package(raw, s.digest(raw))

    def test_backup_overlaps_refused(self):
        with self.assertRaises(s.Refused):
            s.Installer(self.root, backup='/opt/sp7-research/BACKUP')

    def test_backup_policy_rejects_memory_and_internal_storage(self):
        for fs in ['tmpfs', 'ramfs', 'overlay', 'unknown', 'btrfs']:
            self.assertFalse(s.backup_policy({'filesystem': fs}))
        good = {'filesystem': 'ext4', 'root_disks': ['internal'], 'backup_disks': ['usb'], 'usb_transport': True}
        self.assertTrue(s.backup_policy(good))
        self.assertFalse(s.backup_policy(dict(good, backup_disks=['internal'])))
        self.assertFalse(s.backup_policy(dict(good, usb_transport=False)))
        self.assertFalse(s.backup_policy(dict(good, root_disks=[])))
        for fs in ['nfs', 'nfs4', 'cifs', 'fuse.sshfs']:
            self.assertTrue(s.backup_policy({'filesystem': fs}))

    def test_writable_managed_parent_refused(self):
        (self.root / 'opt').mkdir(mode=0o777)
        (self.root / 'opt').chmod(0o777)
        with self.assertRaises(s.Refused):
            self.install()

    def test_changed_identity_under_lock_refused(self):
        self.install()
        with self.assertRaises(s.Refused):
            self.manager.transact(self.second, s.digest(self.second), expected_current=None)


def real_mount_integration():
    """Root VM only. Exercises real separate filesystems with no mocked st_dev."""
    assert os.geteuid() == 0 and os.uname().release == s.KERNEL
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        fixture = Setup('test_install_upgrade_uninstall_and_restore')
        fixture.setUp()
        try:
            fixture.check.stop()
            manager = fixture.manager
            # VM-only persistence/topology injection. The filesystem transaction
            # still crosses a real mount; this is not a physical backup certificate.
            manager.storage_facts = lambda: {'filesystem': 'nfs'}
            manager.backup.mkdir(parents=True)
            subprocess.run(['mount', '-t', 'tmpfs', '-o', 'size=32m,mode=0700,nodev,nosuid,noexec',
                            'tmpfs', str(manager.backup)], check=True)
            try:
                assert manager.backup.stat().st_dev != root.stat().st_dev
                manager.transact(fixture.first, s.digest(fixture.first))
                r = manager.transact(fixture.second, s.digest(fixture.second))
                manager.rollback(r['transaction'])
                r = manager.transact()
                manager.rollback(r['transaction'])
                assert manager.current()['manifest']['version'] == '0.1.0'
                manager.transact()
                assert manager.current() is None
                assert list(manager.backup.glob('*/transaction.json'))
            finally:
                subprocess.run(['umount', str(manager.backup)], check=True)
        finally:
            fixture.doCleanups()
    print('REAL_FILESYSTEM_TRANSACTION_PASS', flush=True)


if __name__ == '__main__':
    if '--real-mount' in sys.argv:
        real_mount_integration()
    else:
        unittest.main()
