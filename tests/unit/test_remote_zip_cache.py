import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
import pytest
from dataset_atlas.storage.remote_zip import RemoteZipMemberCache


class CountingSource(io.BytesIO):
    def __init__(self, payload):
        super().__init__(payload)
        self.bytes_read = 0

    def read(self, size=-1):
        result = super().read(size)
        self.bytes_read += len(result)
        return result


def archive():
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for i in range(2000):
            z.writestr(f"images/{i}.png", f"native {i}".encode())
    return out.getvalue()


def test_repeated_and_parallel_reads_reuse_only_the_directory():
    payload = archive()
    cache = RemoteZipMemberCache()
    spec = {
        "etag": '"immutable"',
        "url": "https://example.com/data.zip",
        "bytes": len(payload),
    }
    with CountingSource(payload) as source:
        assert cache.read(source, spec, "images/1.png", 100) == b"native 1"
        cold = source.bytes_read

    def read(i):
        with CountingSource(payload) as source:
            assert (
                cache.read(source, spec, f"images/{i}.png", 100)
                == f"native {i}".encode()
            )
            return source.bytes_read

    with ThreadPoolExecutor(max_workers=4) as pool:
        warm = list(pool.map(read, range(12)))
    assert max(warm) < 100 < cold
    with CountingSource(payload) as source:
        assert (
            cache.read(source, {**spec, "etag": '"new"'}, "images/1.png", 100)
            == b"native 1"
        )
        assert source.bytes_read == cold


def test_cached_directory_still_checks_member_crc_and_size():
    payload = archive()
    cache = RemoteZipMemberCache()
    with CountingSource(payload) as source:
        cache.read(source, {"etag": '"pinned"'}, "images/1.png", 100)
    with pytest.raises(ValueError, match="byte budget"):
        cache.read(CountingSource(payload), {"etag": '"pinned"'}, "images/1.png", 2)
    damaged = payload.replace(b"native 1", b"BROKEN 1", 1)
    with pytest.raises(zipfile.BadZipFile, match="CRC"):
        cache.read(CountingSource(damaged), {"etag": '"pinned"'}, "images/1.png", 100)


def test_directory_cache_eviction_and_oversize_rejection():
    payload = archive()
    cache = RemoteZipMemberCache(max_archives=1)
    for etag in ['"first"', '"second"']:
        cache.read(CountingSource(payload), {"etag": etag}, "images/1.png", 100)
    assert len(cache.entries) == 1
    with pytest.raises(ValueError, match="metadata budget"):
        RemoteZipMemberCache(max_directory_bytes=20).read(
            CountingSource(payload), {}, "images/1.png", 100
        )
