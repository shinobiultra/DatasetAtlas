"""The range reader retries connection-level timeouts a bounded number of times and never retries a refusal.

A degraded link makes connect, TLS and read time out although the source is healthy. Three attempts with a fixed
backoff are enough to ride out a hiccup; more would hide an outage. HTTP 401, 403 and 404 are answers, not
hiccups, so they are raised at once. Bytes are counted only for ranges that arrived complete: what a timed-out
attempt had received before it failed is not counted (it is discarded and the whole range is requested again).
"""
import io
from urllib.parse import urlsplit

import pytest

from dataset_atlas.storage.ranges import HttpsRangeReader

PAYLOAD = bytes(range(256)) * 8


def transport(monkeypatch, script):
    """`script` lists what each attempt does: 'timeout-connect', 'timeout-response', 'timeout-body', an int status, or 'ok'."""
    attempts, sleeps, closed = [], [], []

    class Response(io.BytesIO):
        def __init__(self, status, start, end, fail_body=False):
            super().__init__(PAYLOAD[start:end + 1])
            self.status, self.will_close, self.fail_body = status, True, fail_body
            self.headers = {'ETag': '"v1"', 'Content-Range': f'bytes {start}-{end}/{len(PAYLOAD)}', 'Content-Length': str(end - start + 1)}

        def getheader(self, name, default=None):
            return self.headers.get(name, default)

        def read(self, size=-1):
            if self.fail_body:
                raise TimeoutError('The read operation timed out')
            return super().read(size)

    class Connection:
        def __init__(self, *args):
            self.number = len(closed) + len(attempts)

        def request(self, method, target, headers):
            self.step = script[len(attempts)] if len(attempts) < len(script) else 'ok'
            attempts.append(self.step)
            self.start, self.end = map(int, headers['Range'][6:].split('-'))
            if self.step == 'timeout-connect':
                raise TimeoutError('_ssl.c:993: The handshake operation timed out')

        def getresponse(self):
            if self.step == 'timeout-response':
                raise TimeoutError('The read operation timed out')
            status = self.step if isinstance(self.step, int) else 206
            return Response(status, self.start, self.end, fail_body=self.step == 'timeout-body')

        def close(self):
            closed.append(self.number)

    monkeypatch.setattr('dataset_atlas.storage.ranges._PinnedHTTPSConnection', Connection)
    monkeypatch.setattr('dataset_atlas.storage.https.HttpsFetcher._destination',
                        lambda self, url: (urlsplit(url).hostname, 443, '93.184.216.34', '/file'))
    monkeypatch.setattr('dataset_atlas.storage.ranges.time.sleep', sleeps.append)
    monkeypatch.setenv('HF_TOKEN', 'hf_fixture_only_never_printed')
    return attempts, sleeps, closed


def reader(**kwargs):
    return HttpsRangeReader('https://huggingface.co/file', size=len(PAYLOAD), etag='"v1"', allowed_hosts=['huggingface.co'],
                            byte_budget=100_000, credential_profile='huggingface', **kwargs)


@pytest.mark.parametrize('failure', ['timeout-connect', 'timeout-response', 'timeout-body'])
def test_a_transient_timeout_is_retried_and_the_range_arrives_whole(monkeypatch, failure):
    attempts, sleeps, closed = transport(monkeypatch, [failure])
    with reader() as source:
        source.seek(10)
        assert source.read(100) == PAYLOAD[10:110]
        # The failed attempt left nothing counted; the retry used a fresh connection.
        assert attempts == [failure, 'ok'] and source.bytes_fetched == 100 and source.timeout_retries == 1
    assert sleeps == [1] and len(closed) >= 2


def test_two_timeouts_in_a_row_still_succeed_with_a_fixed_backoff(monkeypatch):
    attempts, sleeps, _ = transport(monkeypatch, ['timeout-connect', 'timeout-response'])
    with reader() as source:
        assert source.read(50) == PAYLOAD[:50]
    assert attempts == ['timeout-connect', 'timeout-response', 'ok'] and sleeps == [1, 2]


def test_persistent_timeouts_end_in_a_clear_error_after_three_attempts(monkeypatch):
    attempts, sleeps, _ = transport(monkeypatch, ['timeout-connect'] * 10)
    with reader() as source:
        with pytest.raises(ValueError, match=r'timed out.*3 attempts') as failure:
            source.read(50)
        assert source.bytes_fetched == 0
    assert len(attempts) == 3 and sleeps == [1, 2]
    assert 'hf_fixture_only_never_printed' not in str(failure.value)


@pytest.mark.parametrize('status', [401, 403, 404])
def test_a_refusal_or_a_missing_file_is_never_retried(monkeypatch, status):
    attempts, sleeps, _ = transport(monkeypatch, [status] * 5)
    with reader() as source:
        with pytest.raises(ValueError) as failure:
            source.read(50)
    assert attempts == [status] and sleeps == []
    assert (f'received {status}' if status == 404 else f'HTTP {status}') in str(failure.value)


def test_timeouts_and_throttling_share_one_bounded_budget_of_attempts(monkeypatch):
    attempts, _, _ = transport(monkeypatch, [503, 'timeout-connect', 503, 'timeout-response', 503, 503])
    with reader() as source:
        with pytest.raises(ValueError):
            source.read(50)
    assert len(attempts) <= 5
