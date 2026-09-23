"""At most two preparation writers, with exclusive ownership per dataset."""
from contextlib import ExitStack, contextmanager
import fcntl
import hashlib
from pathlib import Path
import time


def try_writer_slot(directory, dataset_id):
    directory = Path(directory)
    identity = hashlib.sha256(dataset_id.encode()).hexdigest()
    dataset_lock = (directory / f'dataset-{identity}.lock').open('a')
    try:
        fcntl.flock(dataset_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        dataset_lock.close()
        return None
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
