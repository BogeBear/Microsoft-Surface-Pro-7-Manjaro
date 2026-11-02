#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Offline, inactive independent SP7 workbench with external rollback snapshots.
Project changes 2026-11-02: independent payload and explicit nonroot MIT interface demo."""
import argparse
import contextlib
import fcntl
import gzip
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tarfile
import uuid

FORMAT = 1
KERNEL = '7.2.11-arch1-1-surface'
BACKUP = '/mnt/sp7-backup/BACKUP/SP7-installer'
PREFIX = '/opt/sp7-research'
LIMIT = 64 * 1024 * 1024
MAX_FILES = 2048


class Refused(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def backup_policy(info):
    if info['filesystem'] in ('nfs', 'nfs4', 'cifs', 'fuse.sshfs'):
        return True
    return (info['filesystem'] in ('ext4', 'xfs', 'ntfs3', 'exfat')
            and bool(info.get('root_disks')) and bool(info.get('backup_disks'))
            and not set(info['root_disks']) & set(info['backup_disks'])
            and info.get('usb_transport') is True)


def physical_disks(dev, seen=None):
    seen = set() if seen is None else seen
    require(dev not in seen, 'Block topology cycle')
    seen.add(dev)
    node = Path('/sys/dev/block') / dev
    require(node.exists(), 'Cannot establish physical backup device topology')
    node = node.resolve(strict=True)
    slaves = list((node / 'slaves').iterdir()) if (node / 'slaves').is_dir() else []
    if slaves:
        result = set()
        for child in slaves:
            result |= physical_disks((child / 'dev').read_text().strip(), set(seen))
        return result
    if (node / 'partition').is_file():
        node = node.parent
    return {str(node)}


def relative(name):
    p = PurePosixPath(name)
    require(isinstance(name, str) and bool(p.parts) and str(p) == name and not p.is_absolute()
            and all(x not in ('.', '..') for x in p.parts) and '\\' not in name
            and not any(ord(c) < 32 for c in name), 'Unsafe archive path')
    return p


def archive_bytes(files):
    """Deterministic regular files only, never links, ownership or executable hooks."""
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode='wb', mtime=0, filename='') as gz:
        with tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as tar:
            for name, (data, mode) in sorted(files.items()):
                relative(name)
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), mode, 0
                tar.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def load_package(raw, expected):
    require(re.fullmatch(r'[a-f0-9]{64}', expected or '') and digest(raw) == expected,
            'Package SHA256 mismatch or missing expected hash')
    require(len(raw) <= LIMIT, 'Compressed package too large')
    files = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
        for item in tar:
            relative(item.name)
            require(item.isreg() and not item.issparse() and item.name not in files,
                    'Archive links, duplicates and special files are forbidden')
            require(item.mode in (0o644, 0o755), 'Unsafe archive permissions')
            total += item.size
            require(0 <= item.size <= LIMIT and total <= LIMIT and len(files) < MAX_FILES,
                    'Archive size or file-count limit exceeded')
            data = tar.extractfile(item).read(item.size + 1)
            require(len(data) == item.size, 'Truncated archive')
            files[item.name] = (data, item.mode)
    require('manifest.json' in files, 'Missing package manifest')
    m = json.loads(files['manifest.json'][0])
    require(isinstance(m, dict), 'Manifest must be an object')
    require(m.get('format') == FORMAT and m.get('profile') == 'inactive-workbench',
            'Unsupported package format/profile; driver activation is not implemented')
    require(isinstance(m.get('version'), str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', m['version']),
            'Invalid package version')
    require(m.get('compatibility') == {'distribution': 'manjaro', 'arch': 'x86_64',
            'product': 'Surface Pro 7', 'kernel': KERNEL, 'python_min': [3, 11], 'glibc_min': [2, 38]},
            'Package compatibility policy differs from reviewed policy')
    require(m.get('activation') == {'camera': False, 'drivers': False, 'login': False,
            'autostart': False}, 'Active package profiles are forbidden')
    rows = m.get('files')
    require(isinstance(rows, dict) and set(rows) == set(files) - {'manifest.json'},
            'Manifest membership mismatch')
    for name, row in rows.items():
        require(name.startswith(('app/', 'licenses/')), 'Unsupported package destination')
        require(row == {'sha256': digest(files[name][0]), 'mode': files[name][1]},
                'Manifest content/mode mismatch: ' + name)
    require(files['manifest.json'][1] == 0o644, 'Invalid manifest permissions')
    require(all(str(parent) not in files for name in files for parent in relative(name).parents
                if str(parent) != '.'), 'Conflicting file and directory archive paths')
    return m, files


class Installer:
    """All mutations are limited to a private prefix and the selected backup tree.

    root is an injected filesystem boundary for offline VM tests. The public CLI
    deliberately provides no alternate root or compatibility-bypass argument.
    """
    def __init__(self, root=Path('/'), backup=BACKUP, event=lambda phase: None):
        self.root = Path(root)
        self.owner = 0 if self.root == Path('/') else os.geteuid()
        require(self.root.is_absolute() and not self.root.is_symlink(), 'Invalid root')
        self.base = self.root / PREFIX.lstrip('/')
        self.event = event
        require(PurePosixPath(backup).is_absolute() and '..' not in PurePosixPath(backup).parts,
                'Backup path must be absolute')
        require('BACKUP' in PurePosixPath(backup).parts, 'Backup path must be under a BACKUP directory')
        self.backup = self.root / backup.lstrip('/')
        require(not self.backup.is_relative_to(self.base) and not self.base.is_relative_to(self.backup),
                'Backup and installation paths overlap')

    def path_guard(self, path, create=False, mode=0o755):
        require(path.is_relative_to(self.root), 'Path outside target filesystem')
        current = self.root
        for part in path.relative_to(self.root).parts:
            current = current / part
            if not current.exists() and not current.is_symlink() and create:
                current.mkdir(mode=mode)
                current.chmod(mode)
            info = current.lstat()
            require(stat.S_ISDIR(info.st_mode) and not current.is_symlink(),
                    'Directory symlink or special file: ' + str(current))
            if path.is_relative_to(self.base) or path.is_relative_to(self.backup):
                require(info.st_uid == self.owner and not info.st_mode & 0o022,
                        'Writable/untrusted ancestor of managed data: ' + str(current))
        return path

    def protected(self, path):
        self.path_guard(path)
        info = path.stat()
        require(info.st_uid == self.owner and not info.st_mode & 0o022,
                'Managed directory has unsafe ownership/permissions')

    def read_file(self, path):
        self.path_guard(path.parent)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as f:
            s = os.fstat(f.fileno())
            require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= LIMIT,
                    'Unsafe file type, hardlink or size')
            # sysfs/proc metadata must not receive a multi-megabyte read request:
            # kernfs can reject the allocation even for a tiny metadata value.
            chunks = []
            total = 0
            while True:
                chunk = f.read(4096)
                if not chunk:
                    return b''.join(chunks)
                total += len(chunk)
                require(total <= LIMIT, 'Read size limit exceeded')
                chunks.append(chunk)

    def write_new(self, path, data, mode=0o600):
        self.path_guard(path.parent)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fchmod(f.fileno(), mode)
            os.fsync(f.fileno())

    def sync(self, path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def atomic_json(self, path, value):
        temp = path.with_name('.json-' + uuid.uuid4().hex)
        self.write_new(temp, encode(value))
        os.replace(temp, path)
        self.sync(path.parent)

    def compatibility(self):
        os_release = self.read_file(self.root / 'usr/lib/os-release').decode()
        fields = dict(line.split('=', 1) for line in os_release.splitlines() if '=' in line)
        distro = fields.get('ID', '').strip('"\'')
        product = self.read_file(self.root / 'sys/devices/virtual/dmi/id/product_name').decode().strip()
        vendor = self.read_file(self.root / 'sys/devices/virtual/dmi/id/sys_vendor').decode().strip()
        # sysfs/proc regular metadata can have st_size=0; no camera node is opened.
        kernel = self.read_file(self.root / 'proc/sys/kernel/osrelease').decode().strip()
        arch = os.uname().machine
        libc = os.confstr('CS_GNU_LIBC_VERSION') or ''
        libc_match = re.fullmatch(r'glibc (\d+)\.(\d+)', libc)
        checks = {'distribution': distro == 'manjaro', 'product': product == 'Surface Pro 7',
                  'vendor': vendor == 'Microsoft Corporation', 'kernel': kernel == KERNEL,
                  'arch': arch == 'x86_64', 'python': sys.version_info >= (3, 11),
                  'glibc': bool(libc_match) and tuple(map(int, libc_match.groups())) >= (2, 38)}
        return {'passed': all(checks.values()), 'checks': checks, 'kernel': kernel,
                'product': product, 'distribution': distro, 'arch': arch, 'libc': libc,
                'optional_dependencies': {'Qt6_QML': (self.root / 'usr/lib/qt6/bin/qml').is_file(),
                    **{name: importlib.util.find_spec(name) is not None for name in ['numpy', 'cv2', 'PIL']}}}

    def current(self):
        if not self.base.exists():
            return None
        self.protected(self.base)
        link = self.base / 'current'
        if not link.exists() and not link.is_symlink():
            return None
        require(link.is_symlink(), 'Unmanaged current path')
        name = os.readlink(link)
        require(re.fullmatch(r'releases/[0-9]+\.[0-9]+\.[0-9]+-[a-f0-9]{12}', name),
                'Unsafe current link')
        m, files = self.read_release(name)
        return {'release': name, 'manifest': m, 'files': files, 'snapshot': archive_bytes(files)}

    def read_release(self, name):
        require(re.fullmatch(r'releases/[0-9]+\.[0-9]+\.[0-9]+-[a-f0-9]{12}', name), 'Unsafe release name')
        folder = self.base / name
        self.protected(folder)
        mraw = self.read_file(folder / 'manifest.json')
        m = json.loads(mraw)
        require(name == 'releases/' + m['version'] + '-' + digest(mraw)[:12], 'Release identity mismatch')
        expected = set(m['files']) | {'manifest.json'}
        expected_dirs = {str(parent) for name in expected for parent in relative(name).parents
                         if str(parent) != '.'}
        files = {}
        for p in folder.rglob('*'):
            require(not p.is_symlink(), 'Unexpected installed symlink')
            if p.is_dir():
                self.protected(p)
                require(p.relative_to(folder).as_posix() in expected_dirs,
                        'Untracked installed directory; preserve and inspect it')
                continue
            rel = p.relative_to(folder).as_posix()
            require(rel in expected, 'Untracked installed file; preserve and inspect it')
            s = p.lstat()
            require(s.st_uid == self.owner and stat.S_ISREG(s.st_mode), 'Unsafe installed ownership/type')
            files[rel] = (self.read_file(p), stat.S_IMODE(s.st_mode))
        require(set(files) == expected, 'Installed files are missing')
        raw = archive_bytes(files)
        load_package(raw, digest(raw))
        return m, files

    def switch(self, release):
        if release is None:
            (self.base / 'current').unlink(missing_ok=True)
        else:
            temp = self.base / ('.link-' + uuid.uuid4().hex)
            os.symlink(release, temp)
            os.replace(temp, self.base / 'current')
        self.sync(self.base)

    @contextlib.contextmanager
    def locked(self):
        self.path_guard(self.base, create=True)
        self.protected(self.base)
        p = self.base / '.lock'
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o644)
            os.fchmod(fd, 0o644)
        except FileExistsError:
            fd = os.open(p, os.O_RDWR | os.O_NOFOLLOW)
        try:
            s = os.fstat(fd)
            require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_uid == self.owner
                    and not s.st_mode & 0o022, 'Unsafe lock file')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused('Another installation transaction holds the lock')
            yield
        finally:
            os.close(fd)

    def use_lease(self):
        """A read-only inherited lease keeps managed previews/tests out of upgrades."""
        self.protected(self.base)
        fd = os.open(self.base / '.lock', os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == self.owner
                    and info.st_nlink == 1 and not info.st_mode & 0o022, 'Unsafe application lock')
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            os.set_inheritable(fd, True)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def stage(self, m, files):
        release = 'releases/' + m['version'] + '-' + digest(files['manifest.json'][0])[:12]
        self.path_guard(self.base / 'releases', create=True)
        dest = self.base / release
        if dest.exists() or dest.is_symlink():
            require(self.read_release(release) == (m, files), 'Existing release differs')
            return release
        staging = dest.parent / ('.staging-' + uuid.uuid4().hex)
        staging.mkdir(mode=0o700)
        try:
            for name, (data, mode) in files.items():
                p = staging / name
                self.path_guard(p.parent, create=True)
                self.write_new(p, data, mode)
            for p in sorted((p for p in staging.rglob('*') if p.is_dir()), reverse=True):
                self.sync(p)
            staging.chmod(0o755)
            self.sync(staging)
            os.rename(staging, dest)
            self.sync(dest.parent)
        except BaseException:
            # This fresh private directory was created only by this transaction.
            # Never apply recursive removal to an existing installed release.
            if staging.exists():
                self.protected(staging)
                require(shutil.rmtree.avoids_symlink_attacks, 'Safe temporary cleanup unavailable')
                shutil.rmtree(staging)
            raise
        return release

    def remove_release(self, release, expected_files):
        if release is None:
            return
        folder = self.base / release
        # Only delete a byte/mode-identical private release, never recursively an unknown tree.
        require(folder.exists(), 'Release missing before cleanup')
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() or p.is_symlink()}
        require(actual == set(expected_files), 'Unexpected cleanup contents')
        for name, (data, mode) in expected_files.items():
            p = folder / name
            require(self.read_file(p) == data and stat.S_IMODE(p.lstat().st_mode) == mode,
                    'Changed cleanup file; preserve it')
        for name in expected_files:
            (folder / name).unlink()
        for p in sorted((p for p in folder.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            p.rmdir()
        folder.rmdir()
        self.sync(folder.parent)

    def check_backup(self):
        require(self.backup.stat().st_dev != self.base.stat().st_dev,
                'Backup must be on a separate mounted filesystem')
        require(backup_policy(self.storage_facts()),
                'Backup must be a supported network filesystem or a separate USB-backed persistent filesystem')

    def storage_facts(self):
        mounts = []
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            left, right = line.split(' - ', 1)
            fields = left.split()
            name = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), fields[4])
            mount = Path(name)
            if self.backup.is_relative_to(mount):
                mounts.append((len(mount.parts), right.split()[0]))
        require(bool(mounts), 'Backup mount is unknown')
        filesystem = max(mounts)[1]
        if filesystem in ('nfs', 'nfs4', 'cifs', 'fuse.sshfs'):
            return {'filesystem': filesystem}
        if filesystem not in ('ext4', 'xfs', 'ntfs3', 'exfat'):
            return {'filesystem': filesystem}
        devices = []
        for path in [self.base, self.backup]:
            dev = path.stat().st_dev
            devices.append(physical_disks(f'{os.major(dev)}:{os.minor(dev)}'))
        return {'filesystem': filesystem, 'root_disks': sorted(devices[0]),
                'backup_disks': sorted(devices[1]),
                'usb_transport': all(any(part.startswith('usb') for part in Path(n).parts) for n in devices[1])}

    def transact(self, raw=None, expected=None, expected_current='any', allow_downgrade=False):
        package = load_package(raw, expected) if raw is not None else None
        if package:
            require(self.compatibility()['passed'], 'Unsupported SP7/Manjaro/kernel/Python combination')
        with self.locked():
            old = self.current()
            require(expected_current == 'any' or (old['release'] if old else None) == expected_current,
                    'Active release changed before transaction lock')
            if package and old and old['manifest'] == package[0]:
                return {'status': 'already-installed', 'release': old['release']}
            if package and old:
                new_version = tuple(map(int, package[0]['version'].split('.')))
                old_version = tuple(map(int, old['manifest']['version'].split('.')))
                require(new_version > old_version or allow_downgrade,
                        'Use rollback for a downgrade; changed same-version packages are refused')
            require(package or old, 'Nothing is installed')
            self.path_guard(self.backup, create=True, mode=0o700)
            self.protected(self.backup)
            self.check_backup()
            tx = self.backup / uuid.uuid4().hex
            tx.mkdir(mode=0o700)
            before = old['release'] if old else None
            after = ('releases/' + package[0]['version'] + '-' + digest(package[1]['manifest.json'][0])[:12]) if package else None
            record = {'format': FORMAT, 'before': before, 'after': after, 'phase': 'preparing'}
            if old:
                self.write_new(tx / 'before.tar.gz', old['snapshot'])
                record['before_sha256'] = digest(old['snapshot'])
            if raw:
                self.write_new(tx / 'requested.tar.gz', raw)
                record['requested_sha256'] = expected
            self.atomic_json(tx / 'transaction.json', record)
            self.sync(tx)
            self.sync(self.backup)
            release = None
            try:
                self.event('backup_saved')
                if package:
                    m, files = package
                    release = self.stage(m, files)
                    require(self.read_release(release) == (m, files), 'Staged disk verification failed')
                record.update(after=release, phase='staged')
                self.atomic_json(tx / 'transaction.json', record)
                self.event('staged')
                self.event('before_switch')
                self.switch(release)
                self.event('after_switch')
                self.current()  # Independent full content check, or absent after uninstall.
                record['phase'] = 'committed'
                self.atomic_json(tx / 'transaction.json', record)
            except Exception as error:
                # Process/power loss is recovered explicitly from the persistent transaction.
                self.switch(before)
                record.update(phase='rolled-back', error=type(error).__name__)
                self.atomic_json(tx / 'transaction.json', record)
                if release and release != before:
                    self.remove_release(release, package[1])
                raise
            if old:
                self.remove_release(old['release'], old['files'])
            return {'status': 'installed' if package else 'uninstalled', 'release': release,
                    'transaction': tx.name, 'backup': str(tx), 'activation': 'none'}

    def rollback(self, transaction):
        require(re.fullmatch(r'[a-f0-9]{32}', transaction or ''), 'Invalid transaction ID')
        self.protected(self.backup)
        tx = self.backup / transaction
        self.protected(tx)
        record = json.loads(self.read_file(tx / 'transaction.json'))
        current = self.current()
        name = current['release'] if current else None
        require(name in (record['before'], record['after']), 'A later or unknown release is active')
        if name == record['before']:
            return {'status': 'already-restored', 'release': name}
        raw = self.read_file(tx / 'before.tar.gz') if record['before'] else None
        return self.transact(raw, record.get('before_sha256'), expected_current=name, allow_downgrade=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'plan', 'install', 'status', 'uninstall',
                                          'rollback', 'preview', 'offline-tests'])
    parser.add_argument('--package', type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--backup-root', default=BACKUP)
    parser.add_argument('--transaction')
    args = parser.parse_args(argv)
    manager = Installer(backup=args.backup_root)
    if args.command in ('install', 'uninstall', 'rollback'):
        require(os.geteuid() == 0, 'Use explicit administrator authorization for this command')
        require(sys.flags.isolated, 'Run administrator commands with python3 -I')
    if args.command == 'check':
        result = manager.compatibility()
        print(json.dumps(result, indent=2))
        return 0 if result['passed'] else 1
    if args.command in ('plan', 'install'):
        require(args.package is not None, '--package is required')
        raw = manager.read_file(args.package.absolute())
        m, files = load_package(raw, args.sha256)
        if args.command == 'plan':
            result = {'compatibility': manager.compatibility(), 'version': m['version'],
                      'files': len(files), 'destination': PREFIX, 'backup': args.backup_root,
                      'activation': 'none', 'publication': 'independent-source-experimental-draft'}
        else:
            result = manager.transact(raw, args.sha256)
    elif args.command == 'uninstall':
        result = manager.transact()
    elif args.command == 'rollback':
        result = manager.rollback(args.transaction)
    elif args.command == 'status':
        current = manager.current()
        result = {'installed': bool(current), 'release': current['release'] if current else None,
                  'activation': 'none'}
    else:
        require(os.geteuid() != 0, 'Run previews and tests as an ordinary user')
        lease = manager.use_lease()
        current = manager.current()
        require(current is not None, 'Nothing is installed')
        app = manager.base / current['release'] / 'app'
        if args.command == 'preview':
            program = Path('/usr/lib/qt6/bin/qml')
            require(program.is_file(), 'Qt 6 Declarative is missing')
            os.execv(str(program), [str(program), str(app / 'interface/ui/Demo.qml')])
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        os.execv('/bin/sh', ['/bin/sh', str(app / 'replacement/run-offline-tests.sh')])
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Refused, OSError, ValueError, tarfile.TarError) as error:
        print('STOP: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
