"""At most two preparation writers, with exclusive ownership per dataset."""
from contextlib import ExitStack, contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time


def try_writer_slot(directory, dataset_id, plan_id=None):
    directory = Path(directory)
    identity = hashlib.sha256(dataset_id.encode()).hexdigest()
    dataset_lock = (directory / f'dataset-{identity}.lock').open('a')
    try:
        fcntl.flock(dataset_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        dataset_lock.close()
        return None
    dataset_lock.seek(0);dataset_lock.truncate()
    dataset_lock.write(json.dumps({'pid':os.getpid(),'plan_id':plan_id}))
    dataset_lock.flush()
    lease = ExitStack()
    lease.callback(dataset_lock.close)
    try:
        for index in range(2):
            lock = (directory / f'writer-{index}.lock').open('a')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                lock.close()
                continue
            lease.callback(lock.close)
            return lease.pop_all()
        return None
    finally:
        lease.close()


def dataset_writer_active(directory, dataset_id, *, plan_id=None, expected_pid=None):
    """Check the dataset lease independently of the two shared writer slots."""
    identity = hashlib.sha256(dataset_id.encode()).hexdigest()
    with (Path(directory) / f'dataset-{identity}.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                lock.seek(0);holder=json.loads(lock.read(1000))
            except (OSError,ValueError):return False
            return ((plan_id is not None and holder.get('plan_id')==plan_id)
                or (holder.get('plan_id') is None and expected_pid is not None and holder.get('pid')==expected_pid))
        fcntl.flock(lock, fcntl.LOCK_UN)
        return False


@contextmanager
def transfer_slot(directory, check):
    """Keep a shared download-cache object alive until its source link exists."""
    with (Path(directory) / 'source-transfer.lock').open('a') as lock:
        while True:
            check()
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(.1)
        yield
