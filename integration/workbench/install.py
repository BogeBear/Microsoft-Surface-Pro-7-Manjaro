"""Unprivileged versioned installation inside the IR project only."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from workbench import CHECKPOINT, PROJECT, ensure_host, verify_release


def allowed_checkpoint(raw):
    state = json.loads(raw)
    if (state.get('active') is not False or state.get('user_pause', {}).get('active')
            or state.get('cooling_only') or state.get('migration_hold', {}).get('active')):
        raise RuntimeError('Installation kräver inaktivt projekt utan paus/nedkylning.')


def install(source, destination, checkpoint):
    source, destination, checkpoint = map(Path, (source, destination, checkpoint))
    raw = checkpoint.read_bytes()
    allowed_checkpoint(raw)
    manifest = verify_release(source)
    version = manifest['version']
    if re.fullmatch(r'[a-f0-9]{16}', version) is None:
        raise ValueError('Invalid release name')
    if destination.resolve() != destination:
        raise ValueError('Installation path must not traverse symlinks')
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    releases = destination / 'releases'
    releases.mkdir(mode=0o700, exist_ok=True)
    if releases.resolve() != releases:
        raise ValueError('Release directory must not be a symlink')
    target = releases / version
    if target.exists():
        if verify_release(target) != manifest:
            raise ValueError('Existing release differs')
    else:
        temporary = Path(tempfile.mkdtemp(prefix='.install-', dir=releases))
        try:
            for name in [*manifest['files'], 'manifest.json']:
                dst = temporary / name
                dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                dst.write_bytes((source / name).read_bytes())
                dst.chmod(0o444)
            verify_release(temporary)
            if checkpoint.read_bytes() != raw:
                raise RuntimeError('Checkpoint changed; release not activated')
            temporary.rename(target)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    if checkpoint.read_bytes() != raw:
        raise RuntimeError('Checkpoint changed; release not activated')
    current = destination / 'current.json'
    if current.is_symlink():
        raise ValueError('Current pointer must not be a symlink')
    previous = current.read_bytes() if current.exists() else None
    if previous is not None:
        backup = destination / ('previous-' + hashlib.sha256(previous).hexdigest()[:16] + '.json')
        if backup.exists() and backup.read_bytes() != previous:
            raise ValueError('Backup differs')
        if not backup.exists():
            with backup.open('xb') as stream:
                stream.write(previous)
    data = (json.dumps({'version': version, 'release': str(target)}) + '\n').encode()
    fd, name = tempfile.mkstemp(prefix='.current-', dir=destination)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        if checkpoint.read_bytes() != raw:
            raise RuntimeError('Checkpoint changed; release not activated')
        os.replace(name, current)
    finally:
        if Path(name).exists():
            Path(name).unlink()
    return {'release': str(target), 'version': version, 'checkpoint_unchanged': True,
            'camera_started': False, 'privileged_installation': False,
            'previous_release_preserved': True}


if __name__ == '__main__':
    ensure_host()
    os.umask(0o077)
    print(json.dumps(install(Path(__file__).resolve().parent,
                             PROJECT / 'work/ir-workbench', CHECKPOINT)))
