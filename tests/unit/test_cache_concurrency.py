"""A brand-new workspace serves its first page of media from many threads at once.

The first grid of images fires dozens of simultaneous media requests, each of which opens the same
not-yet-existing cache database. That cold start must never surface as an HTTP 500.
"""
import threading

from dataset_atlas.adapters import core
from dataset_atlas.storage import BoundedCache


def hammer(factory, threads=24):
    barrier, failures = threading.Barrier(threads), []

    def work():
        barrier.wait()
        try:
            factory()
        except Exception as exc:  # the assertion below reports every distinct failure
            failures.append(f'{type(exc).__name__}: {exc}')

    pool = [threading.Thread(target=work) for _ in range(threads)]
    [t.start() for t in pool]
    [t.join() for t in pool]
    return failures


def test_concurrent_first_use_of_one_cache_directory_does_not_fail(tmp_path):
    assert hammer(lambda: BoundedCache(tmp_path / 'fresh', max_bytes=1_000_000)) == []


def test_decoded_media_cache_is_created_once_under_contention(tmp_path):
    root = tmp_path / 'decoded'
    core._DECODED_CACHES.pop(str(root.resolve()), None)
    made = []
    assert hammer(lambda: made.append(core._decoded_cache(root))) == []
    assert len({id(cache) for cache in made}) == 1
