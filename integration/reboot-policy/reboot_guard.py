#!/usr/bin/python3
"""Project reboot entry point: require fresh CPU measurements below 60 C."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import time

BASE = Path(__file__).resolve().parent.parent
STATE = BASE / 'work/resume-state.json'
LIMIT_MC = 60000
HOT_POLL_SECONDS = 300
REQUIRED_LABELS = {'Package id 0', 'Core 0', 'Core 1', 'Core 2', 'Core 3'}


def read_cpu(hwmon=Path('/sys/class/hwmon')):
    devices = [path for path in hwmon.glob('hwmon*')
               if (path / 'name').read_text().strip() == 'coretemp']
    if len(devices) != 1:
        raise RuntimeError('Exactly one readable coretemp device is required')
    readings = {}
    for path in devices[0].glob('temp*_input'):
        stem = path.name.removesuffix('_input')
        label = (path.parent / (stem + '_label')).read_text().strip()
        if label in readings:
            raise RuntimeError('Duplicate CPU temperature label')
        value = int(path.read_text().strip())
        if not 0 < value < 130000:
            raise RuntimeError('Implausible CPU temperature')
        for suffix in ('_fault', '_crit_alarm'):
            alarm = path.parent / (stem + suffix)
            if alarm.exists() and int(alarm.read_text().strip()) != 0:
                raise RuntimeError('CPU temperature sensor fault or alarm')
        readings[label] = value
    if not REQUIRED_LABELS.issubset(readings):
        raise RuntimeError('Incomplete CPU package/core temperature readings')
    maximum = max(readings.values())
    return {'time': datetime.now().astimezone().isoformat(),
            'sensor': str(devices[0]), 'millidegrees_c': readings,
            'maximum_c': maximum / 1000, 'below_limit': maximum < LIMIT_MC}


def cool_samples(reader=read_cpu, sleeper=time.sleep):
    samples = []
    while len(samples) < 3:
        value = reader()
        if not value['below_limit']:
            samples.clear()
            print(json.dumps({'waiting_for_cooling': True, 'limit_c': LIMIT_MC / 1000,
                              'maximum_c': value.get('maximum_c')}), flush=True)
            sleeper(HOT_POLL_SECONDS)
            continue
        samples.append(value)
        if len(samples) < 3:
            sleeper(5)
    return samples


def save_state(value):
    temporary = STATE.with_suffix('.json.reboot-tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(STATE)
    descriptor = os.open(STATE.parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class CheckpointChanged(RuntimeError):
    pass


def require_authorization(state):
    if (state.get('reboots_authorized') is not True or state.get('user_attention_hold')
            or state.get('migration_hold', {}).get('active')):
        raise CheckpointChanged('Reboot is not authorized or a user hold is active')


def refresh_authorization(previous):
    fresh = json.loads(STATE.read_text())
    require_authorization(fresh)
    request = fresh.get('pending_reboot', {})
    if request.get('command_attempted') or any(
            request.get(key) != previous.get('pending_reboot', {}).get(key)
            for key in ('from_boot', 'reason', 'after_phase', 'after_next_step')):
        raise CheckpointChanged('Reboot plan changed while waiting; review current checkpoint')
    return fresh


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true')
    group.add_argument('--reboot', action='store_true')
    args = parser.parse_args()
    state = json.loads(STATE.read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if args.reboot:
        require_authorization(state)
        request = state.get('pending_reboot', {})
        if request.get('from_boot') != boot or not request.get('reason') or request.get('requested'):
            raise RuntimeError('Missing new reboot plan; do not repeat a reboot attempt')
        if request.get('command_attempted') or any(
                not isinstance(request.get(key), str) or not request[key].strip()
                for key in ('after_phase', 'after_next_step')):
            raise RuntimeError('A new plan must specify the postboot phase and verification steps')
    evidence = {'boot_id': boot, 'limit_c': LIMIT_MC / 1000, 'reboot_requested': False,
                'samples': [], 'camera_used': False}
    try:
        evidence['samples'] = cool_samples()
        if args.reboot:
            state = refresh_authorization(state)
            request = state['pending_reboot']
            # Save the checkpoint, then read all CPU sensors once more just
            # before invoking logind. A check result is never reused later.
            state['phase'] = request['after_phase']
            state['pending_reboot']['requested'] = True
            state['pending_reboot']['temperature_samples'] = evidence['samples']
            state['next_step'] = request['after_next_step']
            save_state(state)
            final = read_cpu()
            evidence['final_sample'] = final
            while not final['below_limit']:
                state['phase'] = 'reboot_waiting_for_cpu_cooling'
                state['pending_reboot']['requested'] = False
                save_state(state)
                time.sleep(HOT_POLL_SECONDS)
                evidence['samples'] = cool_samples()
                final = read_cpu()
                evidence['final_sample'] = final
            state = refresh_authorization(state)
            request = state['pending_reboot']
            state['phase'] = request['after_phase']
            state['pending_reboot']['requested'] = True
            state['pending_reboot']['temperature_samples'] = evidence['samples']
            state['pending_reboot']['final_temperature_sample'] = final
            state['pending_reboot']['command_attempted'] = True
            state['next_step'] = request['after_next_step']
            save_state(state)
            print(json.dumps({'reboot_guard_passed': True, 'final_cpu_c': final['maximum_c']}), flush=True)
            result = subprocess.run(['/usr/bin/systemctl', 'reboot'], capture_output=True, text=True, timeout=20)
            if result.returncode:
                raise RuntimeError('Reboot command failed: ' + result.stderr.strip())
            evidence['reboot_requested'] = True
        else:
            print(json.dumps(evidence), flush=True)
    except Exception as exc:
        evidence['error'] = str(exc)
        if args.reboot and not isinstance(exc, CheckpointChanged):
            state['phase'] = 'reboot_withheld'
            state['pending_reboot']['failure'] = str(exc)
            # Keep requested=True after a command attempt, preventing a blind
            # repeat. Pure temperature failures can be retried after cooling.
            if not state['pending_reboot'].get('command_attempted'):
                state['pending_reboot']['requested'] = False
            state['next_step'] = ('Reboot was withheld. Inspect the recorded reason. If temperature was high, '
                                  'wait for cooling and use reboot_guard.py again with fresh readings. '
                                  'If the reboot command failed, do not retry without new evidence. No camera work.')
            save_state(state)
        raise
    finally:
        folder = BASE / 'outputs/reboot-temperature-checks'
        folder.mkdir(exist_ok=True)
        path = folder / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
        with path.open('x') as stream:
            json.dump(evidence, stream, indent=2)
            stream.write('\n')


if __name__ == '__main__':
    main()
