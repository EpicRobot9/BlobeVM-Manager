#!/usr/bin/env python3
"""Embedded Optimizer module for Blobe dashboard.

Provides:
 - run_once(): perform one optimization pass (guards + optional strict memory enforcement)
 - start_background_loop(): spawn a thread that runs every 15s
 - status(): return {'cfg':..., 'stats':..., 'lastRestart': ...}
 - set_config(key, val): update persisted config
 - tail_logs(): return optimizer log contents

This is a Python port of the previous Node optimizer so it runs inside the Flask process.
"""
import os
import json
import time
import threading
import subprocess
import re

STATE_DIR = os.environ.get('BLOBEDASH_STATE', '/opt/blobe-vm')
LOG_DIR = '/var/blobe/logs/optimizer'
CFG_PATH = os.path.join(STATE_DIR, '.optimizer.json')
RESTART_META_DIR = os.path.join(STATE_DIR, '.optimizer_restarts')
LAST_RESTART_PATH = os.path.join(STATE_DIR, '.optimizer_last_restart')
LAST_RUN_PATH = os.path.join(STATE_DIR, '.optimizer_last_run.json')
ACTION_META_DIR = os.path.join(STATE_DIR, '.optimizer_actions')
ACTIVITY_META_DIR = os.path.join(STATE_DIR, '.optimizer_activity')
PROFILE_META_PATH = os.path.join(STATE_DIR, '.optimizer_profiles.json')
HISTORY_META_PATH = os.path.join(STATE_DIR, '.optimizer_history.json')

DEFAULT_CFG = {
    'enabled': True,
    'guards': {'memory': True, 'cpu': True, 'swap': True, 'health': True},
    'schedulerEnabled': True,
    'restartIntervalHours': 24,
    'strictMemoryLimit': False,
    'memoryLimit': '1g',
    'memorySwappiness': 10,
    'containerRestartCooldownMinutes': 10,
    'guardCooldownSeconds': 300,
    'maxActionsPerRun': 3,
    'hostCpuSoftLimit': 75,
    'hostCpuHardLimit': 90,
    'minAvailableMemoryMb': 2048,
    'maxSwapPercent': 10,
    'protectActiveVms': True,
    'activityWindowSeconds': 300,
    'idleGraceSeconds': 1800,
    'blockStartsOnPressure': True,
    'allowForceStartUnderPressure': True,
    'protectedRestartCooldownSeconds': 900,
}


def ensure_log_dir():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception:
        pass


def log(msg: str):
    ensure_log_dir()
    ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
    line = f'[{ts}] {msg}\n'
    try:
        with open(os.path.join(LOG_DIR, 'optimizer.log'), 'a') as f:
            f.write(line)
    except Exception:
        pass


def load_config():
    try:
        with open(CFG_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return dict(DEFAULT_CFG)


def save_config(cfg: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(CFG_PATH), exist_ok=True)
        with open(CFG_PATH, 'w') as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception as e:
        log(f'failed saving cfg: {e}')
        return False


def _docker_ps_names():
    try:
        out = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True)
        return [l.strip() for l in out.splitlines() if l.strip()]
    except Exception:
        return []


def _list_vm_names():
    names = set()
    inst_root = os.path.join(STATE_DIR, 'instances')
    try:
        if os.path.isdir(inst_root):
            for n in os.listdir(inst_root):
                if os.path.isdir(os.path.join(inst_root, n)):
                    names.add(n)
    except Exception:
        pass
    for cname in _docker_ps_names():
        if cname.startswith('blobevm_'):
            names.add(cname[len('blobevm_'):])
    return sorted(names)


def _read_json_file(path, default):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return default


def _write_json_file(path, payload):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(payload, f, indent=2)
        return True
    except Exception as e:
        log(f'failed writing json file {path}: {e}')
        return False


def load_profiles():
    data = _read_json_file(PROFILE_META_PATH, {})
    if isinstance(data, dict):
        return data
    return {}


def set_vm_profile(name: str, profile: str):
    profile = (profile or 'desktop').strip().lower()
    allowed = {'light', 'desktop', 'interactive', 'gaming', 'background', 'disposable'}
    if profile not in allowed:
        profile = 'desktop'
    profiles = load_profiles()
    profiles[name] = profile
    _write_json_file(PROFILE_META_PATH, profiles)
    return profile


def note_vm_activity(name: str, source: str = 'unknown'):
    try:
        os.makedirs(ACTIVITY_META_DIR, exist_ok=True)
        path = os.path.join(ACTIVITY_META_DIR, re.sub(r'[^A-Za-z0-9_.-]', '_', name) + '.json')
        payload = {
            'name': name,
            'source': source,
            'lastActivityTs': int(time.time()),
        }
        _write_json_file(path, payload)
        return True
    except Exception:
        return False


def _activity_payload(name: str):
    path = os.path.join(ACTIVITY_META_DIR, re.sub(r'[^A-Za-z0-9_.-]', '_', name) + '.json')
    data = _read_json_file(path, {})
    if not isinstance(data, dict):
        data = {}
    return data


def _history_state():
    data = _read_json_file(HISTORY_META_PATH, {'events': [], 'vms': {}})
    if not isinstance(data, dict):
        data = {'events': [], 'vms': {}}
    data.setdefault('events', [])
    data.setdefault('vms', {})
    return data


def _save_history_state(data):
    if not isinstance(data, dict):
        return False
    data.setdefault('events', [])
    data.setdefault('vms', {})
    data['events'] = list(data.get('events') or [])[-120:]
    return _write_json_file(HISTORY_META_PATH, data)


def _record_history_event(event: dict):
    try:
        if not isinstance(event, dict):
            return
        data = _history_state()
        ev = dict(event)
        ev.setdefault('ts', int(time.time()))
        vm_name = ev.get('name') or ev.get('vm')
        if not vm_name and ev.get('container', '').startswith('blobevm_'):
            vm_name = ev['container'][len('blobevm_'):]
        if vm_name:
            ev['vm'] = vm_name
            rec = data['vms'].get(vm_name, {}) if isinstance(data.get('vms'), dict) else {}
            rec.setdefault('history', [])
            rec['lastAction'] = ev.get('action') or ev.get('reason') or 'event'
            rec['lastEventTs'] = ev['ts']
            rec['lastReason'] = ev.get('reason') or ''
            if ev.get('action') in ('restart', 'restart_container'):
                rec['restartCount'] = int(rec.get('restartCount') or 0) + 1
            if ev.get('action') == 'recreate':
                rec['recreateCount'] = int(rec.get('recreateCount') or 0) + 1
            if ev.get('action') == 'warn':
                rec['warnCount'] = int(rec.get('warnCount') or 0) + 1
            rec['history'] = (list(rec.get('history') or []) + [ev])[-20:]
            recent_bad = [x for x in rec['history'] if x.get('action') in ('restart', 'restart_container', 'recreate') and (ev['ts'] - int(x.get('ts') or ev['ts'])) <= 1800]
            rec['unstable'] = len(recent_bad) >= 3
            data['vms'][vm_name] = rec
        data['events'] = (list(data.get('events') or []) + [ev])[-120:]
        _save_history_state(data)
    except Exception as e:
        log(f'failed recording history event: {e}')


def _derive_host_pressure(stats: dict, cfg: dict):
    mem = stats.get('mem') or {}
    swap = stats.get('swap') or {}
    available = mem.get('available', max(0, int(mem.get('total', 0)) - int(mem.get('used', 0))))
    total_mem_mb = int((mem.get('total') or 0) / 1024 / 1024) if mem.get('total') else 0
    available_mb = int(available / 1024 / 1024) if available else 0
    cpu_values = [float(c.get('cpu') or 0.0) for c in (stats.get('containers') or []) if str(c.get('name', '')).startswith('blobevm_')]
    vm_cpu_total = sum(cpu_values)
    swap_total = int(swap.get('total') or 0)
    swap_used = int(swap.get('used') or 0)
    swap_percent = int(round((swap_used / swap_total) * 100)) if swap_total else 0
    score = 0
    reasons = []
    if vm_cpu_total >= float(cfg.get('hostCpuHardLimit', 90)):
        score += 3; reasons.append(f'vm cpu {vm_cpu_total:.1f}% >= hard limit')
    elif vm_cpu_total >= float(cfg.get('hostCpuSoftLimit', 75)):
        score += 2; reasons.append(f'vm cpu {vm_cpu_total:.1f}% >= soft limit')
    if available_mb and available_mb <= int(cfg.get('minAvailableMemoryMb', 2048)):
        score += 2; reasons.append(f'available memory {available_mb}MB below reserve')
    if swap_percent >= int(cfg.get('maxSwapPercent', 10)):
        score += 3; reasons.append(f'swap {swap_percent}% >= max')
    if score >= 5:
        level = 'critical'
    elif score >= 3:
        level = 'pressured'
    elif score >= 1:
        level = 'warm'
    else:
        level = 'healthy'
    return {
        'level': level,
        'score': score,
        'reasons': reasons,
        'vmCpuTotal': round(vm_cpu_total, 2),
        'availableMemoryMb': available_mb,
        'totalMemoryMb': total_mem_mb,
        'swapPercent': swap_percent,
    }


def gather_stats():
    out = {'mem': {}, 'swap': {}, 'containers': []}
    # free -b
    try:
        free = subprocess.check_output(['free', '-b'], text=True)
        lines = free.split('\n')
        memLine = next((l for l in lines if l.lower().startswith('mem:')), '')
        parts = re.split(r'\s+', memLine.strip()) if memLine else []
        if len(parts) >= 3:
            out['mem']['total'] = int(parts[1])
            out['mem']['used'] = int(parts[2])
            if len(parts) >= 7:
                out['mem']['available'] = int(parts[6])
        swapLine = next((l for l in lines if l.lower().startswith('swap:')), '')
        sp = re.split(r'\s+', swapLine.strip()) if swapLine else []
        if len(sp) >= 3:
            out['swap']['total'] = int(sp[1])
            out['swap']['used'] = int(sp[2])
    except Exception:
        pass
    # docker stats
    try:
        d = subprocess.check_output(['docker', 'stats', '--no-stream', '--format', '{{.Name}}|{{.CPUPerc}}|{{.MemPerc}}|{{.MemUsage}}'], text=True)
        for l in d.splitlines():
            if not l.strip():
                continue
            parts = l.split('|')
            if len(parts) >= 4:
                name = parts[0]
                try:
                    cpu = float(parts[1].strip().replace('%', ''))
                except Exception:
                    cpu = 0.0
                try:
                    memperc = float(parts[2].strip().replace('%', ''))
                except Exception:
                    memperc = 0.0
                memusage = parts[3].strip()
                m = re.search(r'([0-9.]+)\s*([KMG]i?)B', memusage)
                memBytes = 0
                if m:
                    n = float(m.group(1)); u = m.group(2).upper()
                    mul = 1024
                    if u.startswith('M'):
                        mul = 1024*1024
                    elif u.startswith('G'):
                        mul = 1024*1024*1024
                    memBytes = int(n * mul)
                out['containers'].append({'name': name, 'cpu': cpu, 'memperc': memperc, 'memBytes': memBytes})
    except Exception:
        pass
    return out


def enforce_strict_memory(cfg: dict):
    try:
        names = _docker_ps_names()
        mem = cfg.get('memoryLimit', '1g')
        swappiness = cfg.get('memorySwappiness', 10)
        for name in names:
            if not name.startswith('blobevm_'):
                continue
            try:
                subprocess.check_call(['docker', 'update', f'--memory={mem}', f'--memory-swap={mem}', f'--memory-swappiness={swappiness}', name])
                log(f'enforce memory on {name} -> {mem} swappiness={swappiness}')
            except Exception as e:
                log(f'docker update failed for {name} : {e}')
    except Exception as e:
        log(f'enforceStrictMemory error {e}')


def _action_allowed(name: str, action: str, cooldown: int):
    try:
        os.makedirs(ACTION_META_DIR, exist_ok=True)
        safe = re.sub(r'[^A-Za-z0-9_.-]', '_', f'{name}.{action}')
        path = os.path.join(ACTION_META_DIR, safe + '.last')
        now = int(time.time())
        last = 0
        if os.path.isfile(path):
            try:
                last = int(open(path, 'r').read().strip())
            except Exception:
                last = 0
        if now - last < max(0, int(cooldown)):
            log(f'skip {action} for {name} (cooldown {cooldown}s)')
            return False
        with open(path, 'w') as f:
            f.write(str(now))
        return True
    except Exception:
        return True


def _record_last_run(events, stats=None):
    try:
        payload = {'ts': int(time.time()), 'events': events or [], 'stats': stats or {}}
        with open(LAST_RUN_PATH, 'w') as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        log(f'failed writing last run: {e}')


def _read_last_restart():
    try:
        with open(LAST_RESTART_PATH, 'r') as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _write_last_restart(ts: int):
    try:
        os.makedirs(os.path.dirname(LAST_RESTART_PATH), exist_ok=True)
        with open(LAST_RESTART_PATH, 'w') as f:
            f.write(str(ts))
    except Exception:
        pass


def perform_scheduled_restart(cfg: dict):
    try:
        last = _read_last_restart()
        now = int(time.time())
        interval = int(cfg.get('restartIntervalHours', 0)) * 3600
        if not cfg.get('schedulerEnabled') or not interval:
            return
        if now - last < interval:
            return
        current_states = _vm_state_map(_derive_vm_states(cfg, gather_stats()))
        names = _docker_ps_names()
        restarted = 0
        cooldown = int(cfg.get('containerRestartCooldownMinutes', 10)) * 60
        maxPerRun = 10
        os.makedirs(RESTART_META_DIR, exist_ok=True)
        for name in names:
            if not name.startswith('blobevm_'):
                continue
            vm_name = name[len('blobevm_'):]
            vm_state = current_states.get(vm_name)
            if _is_vm_protected(vm_state):
                log(f'skip scheduled restart {name} (protected/active VM)')
                continue
            safe = re.sub(r'[^A-Za-z0-9_.-]', '_', name)
            p = os.path.join(RESTART_META_DIR, safe + '.last')
            lastc = 0
            try:
                with open(p, 'r') as f:
                    lastc = int(f.read().strip())
            except Exception:
                lastc = 0
            if now - lastc < cooldown:
                log(f'skip restart {name} (cooldown)')
                continue
            try:
                subprocess.check_call(['docker', 'restart', name])
                restarted += 1
                log(f'scheduler restart {name}')
                try:
                    with open(p, 'w') as f:
                        f.write(str(now))
                except Exception:
                    pass
                time.sleep(2)
                if restarted >= maxPerRun:
                    break
            except Exception as e:
                log(f'scheduler restart failed {name} : {e}')
        if restarted > 0:
            _write_last_restart(now)
            log(f'performed scheduled restart of {restarted} containers')
    except Exception as e:
        log(f'performScheduledRestart error {e}')


def _run_memory_guard(cfg, vm_state_map=None, host_pressure=None):
    # analogous to MemoryGuard.js
    vm_state_map = vm_state_map or {}
    host_pressure = host_pressure or {}
    try:
        out = subprocess.check_output(['docker', 'stats', '--no-stream', '--format', '{{.Name}} {{.MemPerc}} {{.MemUsage}}'], text=True)
        for l in out.splitlines():
            parts = l.strip().split()
            if not parts:
                continue
            name = parts[0]
            if not name.startswith('blobevm_'):
                continue
            vm_name = name[len('blobevm_'):]
            vm_state = vm_state_map.get(vm_name)
            percRaw = parts[1] if len(parts) > 1 else '0%'
            try:
                perc = float(percRaw.replace('%', ''))
            except Exception:
                perc = 0.0
            threshold = cfg.get('memoryThreshold', 60)
            if perc >= threshold:
                if _is_vm_protected(vm_state):
                    log(f'skip memory restart for {name} at {perc}% (protected active VM)')
                    continue
                cooldown = int(cfg.get('guardCooldownSeconds', 300))
                if not _action_allowed(name, 'memory-restart', cooldown):
                    continue
                log(f'Restarting {name} due to memory {perc}%')
                try:
                    subprocess.check_call(['docker', 'restart', name])
                except Exception:
                    pass
                return {'action': 'restart', 'reason': 'memory', 'container': name, 'perc': perc}
    except Exception as e:
        log(f'memguard error {e}')
    return None


def _run_cpu_guard(cfg, vm_state_map=None, host_pressure=None):
    vm_state_map = vm_state_map or {}
    host_pressure = host_pressure or {}
    try:
        out = subprocess.check_output(['docker', 'stats', '--no-stream', '--format', '{{.Name}} {{.CPUPerc}}'], text=True)
        for l in out.splitlines():
            parts = l.strip().split()
            if not parts:
                continue
            name = parts[0]
            if not name.startswith('blobevm_'):
                continue
            vm_name = name[len('blobevm_'):]
            vm_state = vm_state_map.get(vm_name)
            percRaw = parts[1] if len(parts) > 1 else '0%'
            try:
                perc = float(percRaw.replace('%', ''))
            except Exception:
                perc = 0.0
            threshold = cfg.get('cpuThreshold', 70)
            if perc >= threshold:
                if _is_vm_protected(vm_state):
                    log(f'skip cpu restart for {name} at {perc}% (protected active VM)')
                    continue
                if host_pressure.get('level') in ('pressured', 'critical'):
                    log(f'skip cpu restart for {name} at {perc}% while host pressure={host_pressure.get("level")} (prefer relief actions)')
                    continue
                cooldown = int(cfg.get('guardCooldownSeconds', 300))
                if not _action_allowed(name, 'cpu-restart', cooldown):
                    continue
                log(f'Restarting {name} due to cpu {perc}%')
                try:
                    subprocess.check_call(['docker', 'restart', name])
                except Exception:
                    pass
                return {'action': 'restart', 'reason': 'cpu', 'container': name, 'perc': perc}
    except Exception as e:
        log(f'cpuguard error {e}')
    return None


def _run_swap_guard(cfg, vm_state_map=None, host_pressure=None):
    vm_state_map = vm_state_map or {}
    try:
        out = subprocess.check_output(['free', '-b'], text=True)
        lines = out.split('\n')
        swapLine = next((l for l in lines if l.lower().startswith('swap')), '')
        if swapLine:
            parts = re.split(r'\s+', swapLine.strip())
            total = int(parts[1]) if len(parts) > 1 else 0
            used = int(parts[2]) if len(parts) > 2 else 0
            perc = int(round(used / total * 100)) if total else 0
            threshold = cfg.get('swapThreshold', 10)
            if perc >= threshold:
                relief = _stop_idle_pressure_vm(cfg, list(vm_state_map.values()), {'level': 'critical' if perc >= max(threshold, int(cfg.get('maxSwapPercent', 10))) else 'pressured'})
                if relief:
                    relief['reason'] = 'swap-pressure-relief'
                    relief['perc'] = perc
                    return relief
                stats = subprocess.check_output(['docker', 'stats', '--no-stream', '--format', '{{.Name}} {{.MemUsage}}'], text=True)
                heaviest = None; maxBytes = 0
                for l in stats.splitlines():
                    p = l.strip().split()
                    if not p: continue
                    name = p[0]
                    if not name.startswith('blobevm_'): continue
                    vm_name = name[len('blobevm_'):]
                    if _is_vm_protected(vm_state_map.get(vm_name)):
                        continue
                    usage = p[1] if len(p) > 1 else '0'
                    m = re.search(r'([0-9.]+)([KMG]i?)B', usage)
                    bytes_ = 0
                    if m:
                        n = float(m.group(1)); u = m.group(2).upper(); mul = 1024
                        if u.startswith('G'): mul = 1024*1024*1024
                        elif u.startswith('M'): mul = 1024*1024
                        bytes_ = int(n * mul)
                    if bytes_ > maxBytes:
                        maxBytes = bytes_; heaviest = name
                try:
                    subprocess.check_call(['bash', '-c', 'sync; echo 3 > /proc/sys/vm/drop_caches'])
                except Exception:
                    pass
                if heaviest:
                    try:
                        subprocess.check_call(['docker', 'restart', heaviest])
                        log(f'Restarting {heaviest} due to swap {perc}%')
                    except Exception:
                        pass
                    return {'action': 'restart', 'reason': 'swap', 'perc': perc, 'heaviest': heaviest}
    except Exception as e:
        log(f'swapguard error {e}')
    return None


def _run_health_guard(cfg, vm_state_map=None, host_pressure=None):
    vm_state_map = vm_state_map or {}
    try:
        # use blobe-vm-manager list output
        out = subprocess.check_output(['blobe-vm-manager', 'list'], text=True)
        lines = [l for l in out.splitlines() if l.strip().startswith('- ')]
        for l in lines:
            try:
                parts = l[2:].split('->')
                name = parts[0].strip().split()[0]
                url = (parts[2] if len(parts) > 2 else '').strip()
                if not url:
                    continue
                protected = _is_vm_protected(vm_state_map.get(name))
                try:
                    r = subprocess.check_output(['curl', '-Is', '--max-time', '6', url], text=True)
                    if not re.search(r'HTTP\/(1|2) [23]', r):
                        stateDir = STATE_DIR
                        f1 = os.path.join(stateDir, 'instances', name, '.health_warn')
                        f2 = os.path.join(stateDir, 'instances', name, '.health_fail')
                        if not os.path.exists(f1):
                            log(f'Health warn for {name}'); open(f1, 'w').write(str(int(time.time())))
                            return {'action': 'warn', 'name': name}
                        if not os.path.exists(f2):
                            if protected:
                                log(f'skip health restart for {name} (protected active VM); emitting degraded warning only')
                                return {'action': 'warn', 'name': name, 'reason': 'health-protected'}
                            cooldown = int(cfg.get('guardCooldownSeconds', 300))
                            if not _action_allowed(name, 'health-restart', cooldown):
                                return {'action': 'cooldown', 'name': name, 'reason': 'health-restart'}
                            log(f'Health restart container {name}'); open(f2, 'w').write(str(int(time.time())))
                            subprocess.check_call(['docker', 'restart', f'blobevm_{name}'])
                            return {'action': 'restart_container', 'name': name}
                        if protected:
                            return {'action': 'warn', 'name': name, 'reason': 'health-protected-recreate-skipped'}
                        cooldown = int(cfg.get('guardCooldownSeconds', 300))
                        if not _action_allowed(name, 'health-recreate', cooldown):
                            return {'action': 'cooldown', 'name': name, 'reason': 'health-recreate'}
                        log(f'Health recreate {name}')
                        try:
                            subprocess.check_call(['blobe-vm-manager', 'recreate', name])
                        except Exception:
                            pass
                        return {'action': 'recreate', 'name': name}
                except Exception:
                    stateDir = STATE_DIR
                    f1 = os.path.join(stateDir, 'instances', name, '.health_warn')
                    if not os.path.exists(f1):
                        log(f'Health warn (curl fail) for {name}'); open(f1, 'w').write(str(int(time.time())))
                        return {'action': 'warn', 'name': name}
                    if protected:
                        return {'action': 'warn', 'name': name, 'reason': 'health-curlfail-protected'}
                    cooldown = int(cfg.get('guardCooldownSeconds', 300))
                    if not _action_allowed(name, 'health-curlfail-restart', cooldown):
                        return {'action': 'cooldown', 'name': name, 'reason': 'health-curlfail-restart'}
                    log(f'Health restart container (curl fail) {name}'); subprocess.check_call(['docker', 'restart', f'blobevm_{name}'])
                    return {'action': 'restart_container', 'name': name}
            except Exception:
                pass
    except Exception as e:
        log(f'healthguard error {e}')
    return None


def _derive_vm_states(cfg: dict, stats: dict):
    profiles = load_profiles()
    history = _history_state().get('vms', {})
    by_name = {}
    for c in stats.get('containers') or []:
        name = str(c.get('name') or '')
        if name.startswith('blobevm_'):
            by_name[name[len('blobevm_'):]] = c
    now = int(time.time())
    active_window = int(cfg.get('activityWindowSeconds', 300))
    idle_grace = int(cfg.get('idleGraceSeconds', 1800))
    states = []
    for name in _list_vm_names():
        c = by_name.get(name) or {}
        activity = _activity_payload(name)
        last_activity = int(activity.get('lastActivityTs') or 0)
        age = max(0, now - last_activity) if last_activity else None
        profile = profiles.get(name, 'desktop')
        activity_class = 'idle'
        protected = False
        if age is not None and age <= active_window:
            activity_class = 'active'
            protected = bool(cfg.get('protectActiveVms', True)) or profile in ('interactive', 'gaming')
        elif profile in ('interactive', 'gaming') and age is not None and age <= idle_grace:
            activity_class = 'warm'
            protected = bool(cfg.get('protectActiveVms', True))
        pressure = 'low'
        cpu = float(c.get('cpu') or 0.0)
        mem = float(c.get('memperc') or 0.0)
        if cpu >= 85 or mem >= 90:
            pressure = 'high'
        elif cpu >= 60 or mem >= 75:
            pressure = 'medium'
        hist = history.get(name, {}) if isinstance(history, dict) else {}
        state = {
            'name': name,
            'profile': profile,
            'activityClass': activity_class,
            'protected': protected,
            'lastActivityTs': last_activity,
            'secondsSinceActivity': age,
            'cpuPercent': round(cpu, 2),
            'memPercent': round(mem, 2),
            'pressure': pressure,
            'running': bool(c),
            'unstable': bool(hist.get('unstable')),
            'lastAction': hist.get('lastAction'),
            'lastReason': hist.get('lastReason'),
            'lastEventTs': hist.get('lastEventTs'),
            'restartCount': int(hist.get('restartCount') or 0),
            'recreateCount': int(hist.get('recreateCount') or 0),
            'warnCount': int(hist.get('warnCount') or 0),
        }
        states.append(state)
    return states


def _vm_state_map(vm_states):
    return {v.get('name'): v for v in (vm_states or []) if v.get('name')}


def _is_vm_protected(vm_state):
    if not vm_state:
        return False
    return bool(vm_state.get('protected')) or vm_state.get('profile') in ('interactive', 'gaming')


def _stop_idle_pressure_vm(cfg: dict, vm_states, host_pressure):
    if host_pressure.get('level') not in ('pressured', 'critical'):
        return None
    candidates = [
        v for v in (vm_states or [])
        if v.get('running') and v.get('activityClass') == 'idle' and v.get('profile') in ('background', 'disposable', 'light')
    ]
    candidates.sort(key=lambda v: (0 if v.get('profile') in ('background', 'disposable') else 1, -float(v.get('memPercent') or 0), -float(v.get('cpuPercent') or 0)))
    for vm in candidates:
        name = vm.get('name')
        cooldown = int(cfg.get('guardCooldownSeconds', 300))
        if not _action_allowed(name, 'pressure-stop', cooldown):
            continue
        try:
            subprocess.check_call(['docker', 'stop', f'blobevm_{name}'])
            log(f'stopped idle VM {name} due to host pressure {host_pressure.get("level")}')
            return {'action': 'stop', 'reason': 'pressure-relief', 'container': f'blobevm_{name}', 'name': name, 'pressureLevel': host_pressure.get('level')}
        except Exception as e:
            log(f'failed stopping idle VM {name} for pressure relief: {e}')
    return None


def _can_start_vm(cfg: dict, vm_states, host_pressure, profile: str = 'desktop', force: bool = False):
    if force and cfg.get('allowForceStartUnderPressure', True):
        return {'ok': True, 'reason': 'force override allowed'}
    if not cfg.get('blockStartsOnPressure', True):
        return {'ok': True, 'reason': 'start blocking disabled'}
    level = host_pressure.get('level') or 'healthy'
    active_count = len([v for v in (vm_states or []) if v.get('activityClass') in ('active', 'warm') and v.get('running')])
    protected_count = len([v for v in (vm_states or []) if _is_vm_protected(v) and v.get('running')])
    capacity = _estimate_capacity(cfg, {'mem': {'total': int(host_pressure.get('totalMemoryMb', 0)) * 1024 * 1024, 'available': int(host_pressure.get('availableMemoryMb', 0)) * 1024 * 1024}}, vm_states, host_pressure)
    if level == 'critical':
        return {'ok': False, 'reason': 'Host pressure is critical; new VM starts are temporarily blocked.', 'code': 'host-critical', 'capacity': capacity}
    if profile == 'gaming' and capacity.get('estimatedAdditionalGamingSlots', 0) <= 0:
        return {'ok': False, 'reason': 'No safe additional gaming capacity is available on this host right now.', 'code': 'gaming-capacity', 'capacity': capacity}
    if profile in ('interactive', 'gaming') and capacity.get('estimatedAdditionalInteractiveSlots', 0) <= 0:
        return {'ok': False, 'reason': f'There is no safe interactive capacity left for another {profile} VM right now.', 'code': 'interactive-capacity', 'capacity': capacity}
    if level == 'pressured' and profile in ('gaming', 'interactive'):
        return {'ok': False, 'reason': f'Host pressure is high; refusing to start a {profile} VM right now.', 'code': 'profile-blocked', 'capacity': capacity}
    if level == 'pressured' and active_count >= 2 and protected_count >= 1:
        return {'ok': False, 'reason': 'There are already active protected VMs; starting another VM may degrade responsiveness.', 'code': 'capacity-guard', 'capacity': capacity}
    return {'ok': True, 'reason': 'capacity available', 'capacity': capacity}


def _estimate_capacity(cfg: dict, stats: dict, vm_states, host_pressure: dict):
    available_mb = int(host_pressure.get('availableMemoryMb') or 0)
    total_mb = int(host_pressure.get('totalMemoryMb') or 0)
    reserve_mb = int(cfg.get('minAvailableMemoryMb', 2048) or 2048)
    free_for_vms_mb = max(0, available_mb - reserve_mb)
    active = [v for v in (vm_states or []) if v.get('running') and v.get('activityClass') in ('active', 'warm')]
    gaming = [v for v in active if v.get('profile') == 'gaming']
    interactive = [v for v in active if v.get('profile') in ('interactive', 'gaming')]
    soft_limit = float(cfg.get('hostCpuSoftLimit', 75) or 75)
    cpu_headroom = max(0.0, soft_limit - float(host_pressure.get('vmCpuTotal') or 0.0))
    est_game_slots_by_mem = max(0, int(free_for_vms_mb / 3072)) if free_for_vms_mb else 0
    est_game_slots_by_cpu = max(0, int(cpu_headroom / 30.0)) if cpu_headroom else 0
    est_interactive_slots_by_mem = max(0, int(free_for_vms_mb / 2048)) if free_for_vms_mb else 0
    est_interactive_slots_by_cpu = max(0, int(cpu_headroom / 20.0)) if cpu_headroom else 0
    projected_game_capacity = min(est_game_slots_by_mem, est_game_slots_by_cpu)
    projected_interactive_capacity = min(est_interactive_slots_by_mem, est_interactive_slots_by_cpu)
    suitability = 'good'
    if host_pressure.get('level') == 'critical' or projected_game_capacity <= 0:
        suitability = 'poor'
    elif host_pressure.get('level') == 'pressured' or projected_game_capacity == 1:
        suitability = 'tight'
    return {
        'availableMemoryMb': available_mb,
        'reserveMemoryMb': reserve_mb,
        'freeForVmsMb': free_for_vms_mb,
        'cpuHeadroomPercent': round(cpu_headroom, 2),
        'activeVmCount': len(active),
        'interactiveVmCount': len(interactive),
        'gamingVmCount': len(gaming),
        'estimatedAdditionalGamingSlots': projected_game_capacity,
        'estimatedAdditionalInteractiveSlots': projected_interactive_capacity,
        'gamingSuitability': suitability,
        'totalMemoryMb': total_mb,
    }


def _build_recommendations(cfg: dict, stats: dict, vm_states, host_pressure):
    recs = []
    capacity = _estimate_capacity(cfg, stats, vm_states, host_pressure)
    if host_pressure.get('level') in ('pressured', 'critical'):
        recs.append({
            'level': 'warn',
            'title': 'Host pressure is elevated',
            'detail': '; '.join(host_pressure.get('reasons') or ['pressure increasing'])
        })
    if capacity.get('gamingSuitability') == 'poor':
        recs.append({
            'level': 'warn',
            'title': 'Host is currently a poor fit for new gaming sessions',
            'detail': f"Estimated additional gaming slots: {capacity.get('estimatedAdditionalGamingSlots', 0)}; CPU headroom {capacity.get('cpuHeadroomPercent', 0)}%; free VM memory budget {capacity.get('freeForVmsMb', 0)} MB"
        })
    elif capacity.get('gamingSuitability') == 'tight':
        recs.append({
            'level': 'info',
            'title': 'Gaming capacity is tight',
            'detail': f"Estimated additional gaming slots: {capacity.get('estimatedAdditionalGamingSlots', 0)}; active interactive VMs: {capacity.get('interactiveVmCount', 0)}"
        })
    idle_background = [v for v in vm_states if v.get('activityClass') == 'idle' and v.get('profile') in ('background', 'disposable') and v.get('running')]
    if idle_background and host_pressure.get('level') in ('pressured', 'critical'):
        recs.append({
            'level': 'info',
            'title': 'Stop idle background VMs before disruptive recovery',
            'detail': 'Candidates: ' + ', '.join(v['name'] for v in idle_background[:4])
        })
    protected_hot = [v for v in vm_states if v.get('protected') and v.get('pressure') == 'high']
    if protected_hot:
        recs.append({
            'level': 'info',
            'title': 'Protected active VMs are consuming heavy resources',
            'detail': 'Consider increasing host headroom or lowering VM density for: ' + ', '.join(v['name'] for v in protected_hot[:4])
        })
    unstable = [v['name'] for v in vm_states if v.get('unstable')]
    if unstable:
        recs.append({
            'level': 'warn',
            'title': 'Some VMs look unstable',
            'detail': 'Repeated optimizer interventions detected for: ' + ', '.join(unstable[:5])
        })
    unknown_profiles = [v['name'] for v in vm_states if v.get('profile') == 'desktop']
    if unknown_profiles:
        recs.append({
            'level': 'info',
            'title': 'Assign explicit VM profiles',
            'detail': 'Still using default desktop profile: ' + ', '.join(unknown_profiles[:5])
        })
    if not recs:
        recs.append({'level': 'ok', 'title': 'No optimizer recommendations right now', 'detail': 'Host pressure is stable and VM activity looks calm.'})
    return recs[:8]


def run_once():
    cfg = load_config()
    events = []
    max_actions = max(1, int(cfg.get('maxActionsPerRun', 3)))
    try:
        pre_stats = gather_stats()
        host_pressure = _derive_host_pressure(pre_stats, cfg)
        vm_states = _derive_vm_states(cfg, pre_stats)
        vm_state_map = _vm_state_map(vm_states)
        if host_pressure.get('level') in ('pressured', 'critical') and len(events) < max_actions:
            relief = _stop_idle_pressure_vm(cfg, vm_states, host_pressure)
            if relief:
                events.append(relief)
        guards = []
        if cfg.get('guards', {}).get('memory'):
            guards.append(_run_memory_guard)
        if cfg.get('guards', {}).get('cpu') and host_pressure.get('level') != 'critical':
            guards.append(_run_cpu_guard)
        if cfg.get('guards', {}).get('swap'):
            guards.append(_run_swap_guard)
        if cfg.get('guards', {}).get('health'):
            guards.append(_run_health_guard)
        for guard in guards:
            if len(events) >= max_actions:
                log(f'maxActionsPerRun reached ({max_actions}), stopping guard execution early')
                break
            r = guard(cfg, vm_state_map=vm_state_map, host_pressure=host_pressure)
            if r:
                events.append(r)
        if cfg.get('strictMemoryLimit'):
            try:
                enforce_strict_memory(cfg)
            except Exception as e:
                log(f'error enforcing strictMemoryLimit: {e}')
        for ev in events:
            _record_history_event(ev)
        post_stats = gather_stats()
        post_host_pressure = _derive_host_pressure(post_stats, cfg)
        post_vm_states = _derive_vm_states(cfg, post_stats)
        payload_stats = {
            'raw': post_stats,
            'hostPressure': post_host_pressure,
            'vmStates': post_vm_states,
            'capacity': _estimate_capacity(cfg, post_stats, post_vm_states, post_host_pressure),
            'recommendations': _build_recommendations(cfg, post_stats, post_vm_states, post_host_pressure),
            'history': _history_state(),
        }
    except Exception as e:
        log(f'error in run_once: {e}')
        payload_stats = {'raw': gather_stats()}
    _record_last_run(events, payload_stats)
    return events


_loop_thread = None
_loop_lock = threading.Lock()


def _background_loop():
    log('optimizer background loop starting')
    while True:
        try:
            cfg = load_config()
            if cfg.get('enabled'):
                run_once()
            try:
                if cfg.get('schedulerEnabled'):
                    perform_scheduled_restart(cfg)
            except Exception as e:
                log(f'scheduler error {e}')
        except Exception as e:
            log(f'optimizer loop error {e}')
        time.sleep(15)


def start_background_loop():
    global _loop_thread
    with _loop_lock:
        if _loop_thread and _loop_thread.is_alive():
            return False
        t = threading.Thread(target=_background_loop, daemon=True)
        _loop_thread = t
        t.start()
        return True


def status():
    cfg = load_config()
    raw_stats = gather_stats()
    host_pressure = _derive_host_pressure(raw_stats, cfg)
    vm_states = _derive_vm_states(cfg, raw_stats)
    stats = {
        'raw': raw_stats,
        'hostPressure': host_pressure,
        'vmStates': vm_states,
        'capacity': _estimate_capacity(cfg, raw_stats, vm_states, host_pressure),
        'recommendations': _build_recommendations(cfg, raw_stats, vm_states, host_pressure),
        'profiles': load_profiles(),
        'history': _history_state(),
    }
    last = 0
    last_run = {}
    try:
        if os.path.isfile(LAST_RESTART_PATH):
            last = int(open(LAST_RESTART_PATH, 'r').read().strip())
    except Exception:
        last = 0
    try:
        if os.path.isfile(LAST_RUN_PATH):
            last_run = json.load(open(LAST_RUN_PATH, 'r'))
    except Exception:
        last_run = {}
    return {'cfg': cfg, 'stats': stats, 'lastRestart': last, 'lastRun': last_run}


def set_config(key, val):
    cfg = load_config()
    if key == 'guards' and isinstance(val, dict):
        cfg.setdefault('guards', {}).update(val)
    else:
        cfg[key] = val
    save_config(cfg)
    return True


def tail_logs():
    p = os.path.join(LOG_DIR, 'optimizer.log')
    try:
        if os.path.isfile(p):
            return open(p, 'r').read()
    except Exception:
        pass
    return ''
