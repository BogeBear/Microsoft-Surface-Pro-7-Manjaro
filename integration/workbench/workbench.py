"""Fixed SP7 workspace entry point. Hardware runs still require a reviewed plan."""
from datetime import datetime
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time

PROJECT = Path('/srv/sp7-project/target')
CHECKPOINT = PROJECT / 'work/resume-state.json'
MACHINE = '00000000000000000000000000000000'
RELEASE = Path(__file__).resolve().parent
COMPONENTS = (
    '/usr/local/libexec/sp7-ir-project/helper',
    '/usr/local/libexec/sp7-ir-idle/inspect',
    '/usr/local/libexec/sp7-camera-auth-capture',
    '/usr/local/libexec/sp7-camera-howdy/python/bin/python',
    '/usr/local/lib/howdy', '/usr/local/share/howdy/dlib-data',
    '/etc/howdy/config.ini',
)
STAGES = [
    ['Drivrutiner', 'Installerade; versionskontrolleras mot fast manifest.'],
    ['IR-bildfångst', 'Bildöverföring verifierad i prov; startens tillförlitlighet återstår.'],
    ['Bildkvalitet', '87 bilder insamlade; kvalitetsmått och exponering utreds lokalt.'],
    ['Biometrisk jämförelse', 'Fristående analysmotor fungerar lokalt; oberoende verifiering återstår.'],
    ['Inloggning', 'Aktiveras först efter separat verifiering av hela kedjan.'],
]


def ensure_host():
    if (os.getuid() != 1000 or os.uname().nodename != 'sp7-example'
            or Path('/etc/machine-id').read_text().strip() != MACHINE):
        raise RuntimeError('Detta kommando gäller endast användarkontot på SP7.')


def verify_release(folder=RELEASE):
    manifest = json.loads((folder / 'manifest.json').read_text())
    files = manifest.get('files')
    if (not isinstance(files, dict) or not files or len(files) > 256 or
            manifest.get('version') != hashlib.sha256(
                json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]):
        raise RuntimeError('Ogiltigt versionsmanifest.')
    for name, digest in manifest['files'].items():
        if not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None:
            raise RuntimeError('Ogiltig filkontrollsumma.')
        rel = Path(name)
        file = folder / rel
        if (rel.is_absolute() or '..' in rel.parts or file.resolve() != file
                or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != digest):
            raise RuntimeError('Arbetsinstallationens filkontroll misslyckades: ' + name)
    return manifest


def probe_authorized(state, plan):
    return (state.get('active') is True and not state.get('user_pause', {}).get('active')
            and not state.get('cooling_only') and not state.get('migration_hold', {}).get('active')
            and state.get('phase') == 'reviewed_single_probe_ready'
            and state.get('boot_id') == plan.get('boot_id')
            and state.get('reviewed_presence_plan') == plan)


def last_trial(state):
    candidates = []
    for key, kind in (('latest_sensor_only_result', 'sensor_only'),
                      ('latest_face_result', 'face_capture')):
        path = state.get(key)
        if not isinstance(path, str):
            continue
        file = Path(path)
        if not (file.is_absolute() and file.is_relative_to(PROJECT / 'work')
                and file.resolve() == file and file.is_file() and file.stat().st_size <= 1048576):
            continue
        result = json.loads(file.read_text())
        trial = result.get('trial', {}) if kind == 'sensor_only' else result
        candidates.append((file, kind, result, trial))
    if candidates:
        if len(candidates) > 1:
            # Use event times, never copy time or a hard-coded trial type.
            try:
                def event_time(candidate):
                    stamp = datetime.fromisoformat(candidate[3]['started'])
                    if stamp.tzinfo is None:
                        raise ValueError('Tidszon saknas.')
                    return stamp.timestamp()
                candidates.sort(key=event_time)
            except (KeyError, TypeError, ValueError):
                return {'available': False, 'reason': 'Senaste prov kan inte avgöras från tidsstämplarna.'}
        file, kind, result, trial = candidates[-1]
        summary = {'available': True, 'historical_only': True, 'kind': kind,
                   'result_file': str(file),
                   **{name: trial.get(name) for name in ('started', 'finished', 'received_frames',
                       'capture_attempted', 'counted_session', 'error', 'cleanup_errors',
                       'kernel_teardown_errors', 'strobe_after', 'safe_to_test_front')}}
        if kind == 'sensor_only':
            summary.update(passed=result.get('passed'), shutdown_verified=result.get('shutdown_verified'))
        else:
            summary['saved_frames'] = trial.get('counted_session', {}).get('saved_frames')
            summary['quality_validated'] = False
        return summary
    output = state.get('reviewed_presence_plan', {}).get('output_dir')
    if not isinstance(output, str):
        return {'available': False}
    folder = Path(output)
    file = folder / 'counted-1-attempt-1/result.json'
    if (not folder.is_absolute() or not folder.is_relative_to(PROJECT / 'work')
            or file.resolve() != file or not file.is_file()):
        return {'available': False}
    if file.stat().st_size > 1048576:
        return {'available': False, 'reason': 'Resultatfilen är för stor.'}
    result = json.loads(file.read_text())
    return {'available': True, 'historical_only': True,
            'result_file': str(file),
            **{name: result.get(name) for name in ('started', 'finished',
                'capture_attempted', 'counted_session', 'error', 'cleanup_errors',
                'kernel_teardown_errors', 'strobe_after', 'safe_to_test_front')}}


def diagnose():
    ensure_host()
    manifest = verify_release()
    state = json.loads(CHECKPOINT.read_text())
    report = {'schema': 1, 'checked_at': time.time(), 'version': manifest['version'],
              'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
              'kernel': os.uname().release, 'phase': state.get('phase'),
              'active': state.get('active'), 'stages': STAGES,
              'camera_started': False, 'capture_authorized': False,
              'components_present': {name: Path(name).exists() for name in COMPONENTS}}
    try:
        report['last_trial'] = last_trial(state)
    except (OSError, ValueError) as exc:
        report['last_trial'] = {'available': False, 'reason': str(exc)}
    # Avoid competing inventory/SSH processes while a probe or cooling is active.
    if state.get('active') or state.get('cooling_only'):
        report['inspection'] = {'complete': False, 'reason': 'Aktivt prov/arbete eller nedkylning; ingen parallell kontroll.'}
        return report
    sys.path.insert(0, str(RELEASE / 'probe'))
    sys.path.insert(0, str(RELEASE / 'presence-dialog'))
    import deployment_binding
    import idle_client
    import presence
    try:
        files = deployment_binding.verify_deployment()
        report['deployment'] = {'verified': True, 'bound_files': len(files)}
    except Exception as exc:
        report['deployment'] = {'verified': False, 'reason': str(exc)}
    try:
        idle = idle_client.read_idle()
        report['inspection'] = idle
        presence.require_idle(idle, report['boot_id'], time.monotonic())
        report['idle_at_check'] = True
    except Exception as exc:
        report['idle_at_check'] = False
        report['inspection_error'] = str(exc)
    report['note'] = 'Ögonblicksbild; gäller inte som Redo, provtillstånd eller avslutskvitto.'
    return report


def launch_plan(path):
    ensure_host()
    verify_release()
    path = Path(path)
    if (not path.is_absolute() or path.resolve() != path or
            not path.is_relative_to(PROJECT / 'work')):
        raise RuntimeError('Planen måste finnas utan länkar i SP7-projektets work-mapp.')
    sys.path.insert(0, str(RELEASE / 'presence-dialog'))
    import reviewed_plan
    import live_runner
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    plan, digest = reviewed_plan.load(path, boot, live_runner.required_ui_files())
    if not probe_authorized(json.loads(CHECKPOINT.read_text()), plan):
        raise RuntimeError('Ingen aktuell granskad provplan är aktiverad. Befintlig spärr kvarstår.')
    # The runner rechecks checkpoint, adapter files, fresh idle and physical
    # presence. This command never manufactures a Redo click or edits checkpoint.
    env = {k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'LD_'))}
    env.update(PATH='/usr/bin:/bin', PYTHONDONTWRITEBYTECODE='1')
    return subprocess.call(['/usr/bin/python3', '-B',
                            str(RELEASE / 'presence-dialog/live_runner.py'), '--plan', str(path)], env=env)


def save_report(report):
    folder = PROJECT / 'work/ir-workbench/.reports'
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if folder.resolve() != folder:
        raise RuntimeError('Rapportmappen får inte vara en symbolisk länk.')
    path = folder / ('status-' + str(time.time_ns()) + '.json')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write('\n')
    return path


def gui():
    ensure_host()
    verify_release()
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, GLib, Gio
    app = Gtk.Application(application_id='local.sp7.IRWorkbench', flags=Gio.ApplicationFlags.NON_UNIQUE)
    def activate(app):
        window = Gtk.ApplicationWindow(application=app, title='SP7 – IR-arbetsbänk')
        window.set_default_size(820, 620)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(box, 'set_margin_' + side)(16)
        box.append(Gtk.Label(label='IR-sensor → bildfångst → bildkvalitet → biometrisk verifiering', wrap=True))
        box.append(Gtk.Label(label='Statuskontrollen startar ingen kamera. Ansiktsprov kräver Redo; sensorprov utan bildlagring kan köras obemannat.', wrap=True))
        view = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        text = view.get_buffer()
        text.set_text('\n\n'.join(name + ': ' + status for name, status in STAGES))
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(view); box.append(scroll)
        results = queue.Queue()
        button = Gtk.Button(label='Kontrollera installation och viloläge')
        def inspect(*_):
            button.set_sensitive(False)
            def task():
                try:
                    report = diagnose()
                    path = save_report(report)
                    results.put(json.dumps(report, ensure_ascii=False, indent=2) + '\n\nSparat: ' + str(path))
                except Exception as exc:
                    results.put('Kontroll misslyckades: ' + str(exc))
            threading.Thread(target=task, daemon=True).start()
        button.connect('clicked', inspect); box.append(button)
        guide = Gtk.Button(label='Visa arbetsgång och nästa steg')
        guide.connect('clicked', lambda *_: text.set_text((RELEASE / 'ARBETSGANG.txt').read_text()))
        box.append(guide)
        window.set_child(box)
        alive = [True]
        def close(*_):
            alive[0] = False
            return False
        window.connect('close-request', close)
        def mapped(*_):
            save_report({'window_mapped': True, 'pid': os.getpid(), 'camera_started': False,
                         'type': 'workbench-ui', 'version': verify_release()['version']})
        window.connect('map', mapped)
        def poll():
            if not alive[0]:
                return False
            try:
                text.set_text(results.get_nowait())
                button.set_sensitive(True)
            except queue.Empty:
                pass
            return True
        GLib.timeout_add(200, poll)
        window.present()
    app.connect('activate', activate)
    app.run([])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['gui', 'status', 'describe', 'probe'])
    parser.add_argument('--plan', type=Path)
    args = parser.parse_args()
    if args.command == 'describe':
        print(json.dumps(STAGES, ensure_ascii=False, indent=2))
    elif args.command == 'status':
        report = diagnose()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.command == 'gui':
        gui()
    elif args.command == 'probe':
        if not args.plan:
            parser.error('probe kräver --plan; arbetsbänken skapar aldrig en provplan.')
        return launch_plan(args.plan)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
