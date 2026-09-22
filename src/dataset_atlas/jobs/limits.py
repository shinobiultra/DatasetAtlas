"""Kernel CPU limit plus an independent worker RSS/wall-time watchdog."""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import threading
import time

DEFAULTS = {'max_rss_bytes': 8_000_000_000, 'max_cpu_seconds': 3600, 'max_wall_seconds': 7200}
MAXIMA = {'max_rss_bytes': 256_000_000_000, 'max_cpu_seconds': 604800, 'max_wall_seconds': 604800}


def limits(config):
    result = {key: config.get(key, value) for key, value in DEFAULTS.items()}
    for key, value in result.items():
        if type(value) is not int or not 1 <= value <= MAXIMA[key]:
            raise ValueError(f'{key} must be a positive integer no greater than {MAXIMA[key]}')
    return result


def process_tree_rss(pid):
    total = 0
    queue = [pid]
    seen = set()
    while queue:
        current = queue.pop()
        if current in seen:continue
        seen.add(current)
        if len(seen) > 1024:raise ValueError('Worker exceeded process count bound')
        try:
            for line in Path(f'/proc/{current}/status').read_text().splitlines():
                if line.startswith('VmRSS:'):total += int(line.split()[1]) * 1024
            queue.extend(int(value) for value in Path(f'/proc/{current}/task/{current}/children').read_text().split())
        except FileNotFoundError:
            continue
    return total


def install(config, stage):
    """Must run inside a dedicated worker process group before model imports.

    RSS is sampled every 100ms and may overshoot between samples. CPU time uses
    RLIMIT_CPU. This deliberately does not mislabel RLIMIT_AS/RSS as a RAM cap.
    """
    import resource
    bounds = limits(config)
    cpu = bounds['max_cpu_seconds']
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    started = time.monotonic()
    def terminate(kind, observed):
        path = Path(stage) / 'resource-error.receipt'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'type': 'ResourceLimitExceeded', 'resource': kind,
            'limit': bounds[kind], 'observed': observed, 'message': f'Worker exceeded {kind}'}))
        temporary.replace(path)
        if os.getpgrp() == os.getpid():os.killpg(os.getpgrp(), signal.SIGKILL)
        os._exit(87)
    signal.signal(signal.SIGXCPU, lambda *_: terminate('max_cpu_seconds', cpu))
    def watch():
        while True:
            elapsed = time.monotonic() - started
            if elapsed > bounds['max_wall_seconds']:terminate('max_wall_seconds', elapsed)
            rss = process_tree_rss(os.getpid())
            if rss > bounds['max_rss_bytes']:terminate('max_rss_bytes', rss)
            time.sleep(.1)
    threading.Thread(target=watch, daemon=True, name='atlas-resource-watchdog').start()


from functools import lru_cache


@lru_cache(maxsize=1)
def cgroup_available():
    """Probe actual user-manager delegation, not merely systemd's installation."""
    import shutil
    import subprocess
    import sys
    if not shutil.which('systemd-run') or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        return False
    try:
        result=subprocess.run(['systemd-run','--user','--scope','--quiet','--property=MemoryMax=8000000000',
            '--property=MemorySwapMax=0',sys.executable,'-c',
            "from pathlib import Path; p=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split(':')[-1].lstrip('/'); assert (p/'memory.max').read_text().strip()=='8000000000' and (p/'memory.swap.max').read_text().strip()=='0'"],capture_output=True,timeout=5)
        return result.returncode==0
    except (OSError,subprocess.TimeoutExpired):
        return False


def worker_command(command, config):
    bounds=limits(config)
    if cgroup_available():
        return ['systemd-run','--user','--scope','--quiet',f"--property=MemoryMax={bounds['max_rss_bytes']}",
            '--property=MemorySwapMax=0','--property=TasksMax=512','--',*command]
    return command


def enforcement():
    return ('kernel cgroup memory cap including descendants; swap disabled' if cgroup_available()
        else 'process-tree RSS watchdog, 100 ms sampling; transient overshoot possible')
