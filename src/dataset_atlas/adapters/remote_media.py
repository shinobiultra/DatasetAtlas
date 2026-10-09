"""Original archives too large to download, read by HTTPS ranges bound to a strong ETag.

An adapter whose source ZIP is several gigabytes (COCO val2014 is 6.6 GB, GQA's images 21.8 GB) declares it as
`{url, bytes, etag, allowed_hosts}`. Atlas reads the ZIP's directory and the few members a user inspects, never the
whole file. A strong ETag is a consistency fingerprint (the file did not change between reads), not a content hash,
and every record says so.
"""
from __future__ import annotations
from pathlib import Path
import zipfile


class RemoteZip:
    REQUIRED = ('url', 'bytes', 'etag', 'allowed_hosts')

    def __init__(self, spec: dict, cache_root: str | Path, cache_bytes: int = 1_000_000_000):
        if not isinstance(spec, dict) or not all(spec.get(key) for key in self.REQUIRED):
            raise ValueError('A remote archive requires a URL, size, strong ETag and allowed hosts')
        self.spec, self.cache_root, self.cache_bytes = spec, Path(cache_root), cache_bytes

    @property
    def etag(self) -> str:
        return self.spec['etag']

    def reader(self, budget: int):
        """An ETag-bound range reader that refuses to exceed `budget` transferred bytes."""
        from dataset_atlas.storage import BoundedCache
        from dataset_atlas.storage.ranges import HttpsRangeReader
        cache = BoundedCache(self.cache_root, max_bytes=self.cache_bytes)
        return HttpsRangeReader(self.spec['url'], size=self.spec['bytes'], etag=self.spec['etag'],
                                allowed_hosts=self.spec['allowed_hosts'], byte_budget=budget, cache=cache)

    def names(self, budget: int) -> list[str]:
        """Every member name, from the central directory alone."""
        from dataset_atlas.storage.ranges import SmallReadBuffer
        with self.reader(budget) as remote, zipfile.ZipFile(SmallReadBuffer(remote)) as archive:
            return archive.namelist()

    def read(self, member: str, max_bytes: int, budget: int) -> bytes:
        """One member's original bytes; the ZIP's own CRC is checked."""
        from dataset_atlas.storage.ranges import SmallReadBuffer
        from dataset_atlas.storage.remote_zip import REMOTE_ZIP_MEMBERS
        with self.reader(budget) as remote:
            return REMOTE_ZIP_MEMBERS.read(SmallReadBuffer(remote), self.spec, member, max_bytes)
