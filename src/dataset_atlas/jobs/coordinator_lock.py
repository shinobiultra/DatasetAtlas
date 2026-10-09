"""One process coordinates a workspace's runs at a time (SPEC section 3.2).

Starting a workbench recovers every queued or running run, and whichever process lists a run registers the output its worker staged. Two
coordinators on one workspace therefore both consume the same staged files: one wins, the other fails mid-registration and marks a run that
actually finished as partial. The lock is an advisory `flock` held for the life of the process, so the operating system releases it if the
process dies. It guards the process entry points (`atlas serve`, `atlas analyze`, `atlas export`); library code and tests are unaffected.
"""
from __future__ import annotations
import fcntl
import os
from pathlib import Path


class CoordinatorBusy(ValueError):
    """Another process already coordinates this workspace."""


def acquire_coordinator_lock(work_dir: Path):
    """Return an open lock handle to keep for the process lifetime, or raise CoordinatorBusy naming the holder."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    handle = (work_dir / '.coordinator.lock').open('a+')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.seek(0)
        holder = handle.read().strip() or 'unknown'
        handle.close()
        raise CoordinatorBusy(
            f'Another Atlas process (pid {holder}) is already coordinating the workspace at {work_dir.parent}. '
            'Use that workbench, stop it first, or choose a different --root: two coordinators would both register the same runs.') from None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle
