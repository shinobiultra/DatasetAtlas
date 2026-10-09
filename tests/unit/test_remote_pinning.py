import threading

import pytest

from dataset_atlas.preparation.remote import pin_remote_files


def test_pinning_overlaps_requests_without_changing_source_order(monkeypatch):
    barrier = threading.Barrier(4)
    seen = []
    lock = threading.Lock()

    def fingerprint(url, **kwargs):
        with lock:
            seen.append(url)
        barrier.wait(timeout=3)
        return '"' + url + '"'

    monkeypatch.setattr('dataset_atlas.preparation.remote.range_fingerprint', fingerprint)
    files = [{'url': str(i), 'bytes': i, 'source_name': str(i)} for i in range(8)]
    updates = []
    result = pin_remote_files(files, ['example.org'], lambda: None, lambda **x: updates.append(x), workers=4)
    assert [item['url'] for item in result] == [str(i) for i in range(8)]
    assert len(seen) == 8 and updates[-1]['pinned_shards'] == 8
    assert result[3]['etag'] == '"3"'


def test_cancel_does_not_submit_more_batches(monkeypatch):
    seen = []
    def fingerprint(url, **kwargs):
        seen.append(url)
        return '"v1"'
    monkeypatch.setattr('dataset_atlas.preparation.remote.range_fingerprint', fingerprint)
    def check():
        if len(seen) >= 2:
            raise InterruptedError('cancelled')
    files = [{'url': str(i), 'bytes': i, 'source_name': str(i)} for i in range(20)]
    with pytest.raises(InterruptedError):
        pin_remote_files(files, [], check, lambda **x: None, workers=2)
    assert len(seen) <= 2
