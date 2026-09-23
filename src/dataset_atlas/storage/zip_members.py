"""Bounded reuse of verified local ZIP directories for repeated member reads."""
from __future__ import annotations

from collections import OrderedDict
import hashlib
from pathlib import Path
import threading
import zipfile


class ZipMemberCache:
    def __init__(self, max_archives=4, max_directory_bytes=100_000_000):
        self.max_archives = max_archives
        self.max_directory_bytes = max_directory_bytes
        self.entries = OrderedDict()
        self.lock = threading.RLock()

    def close(self):
        with self.lock:
            for archive, _ in self.entries.values():
                archive.close()
            self.entries.clear()

    def read(self, path, member, max_bytes, expected_sha256=None):
        from dataset_atlas.adapters.core import _safe_relative
        member = _safe_relative(member)
        path = Path(path).resolve()
        stat = path.stat()
        key = (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, expected_sha256)
        with self.lock:
            if key not in self.entries:
                with path.open('rb') as stream:
                    # CPython's bounded EOCD/ZIP64 parser reads only the tail. It
                    # lets us reject oversized directories before ZipInfo allocation.
                    end = zipfile._EndRecData(stream)
                    if end is None:raise ValueError('Invalid local ZIP archive')
                    directory_bytes = end[zipfile._ECD_SIZE]
                    if directory_bytes > self.max_directory_bytes or end[zipfile._ECD_ENTRIES_TOTAL] > 1_000_000:
                        raise ValueError('ZIP directory exceeds metadata budget')
                    if expected_sha256:
                        stream.seek(0)
                        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected_sha256:
                            raise ValueError('Local ZIP differs from pinned checksum')
                while self.entries and (len(self.entries) >= self.max_archives or
                        sum(size for _, size in self.entries.values()) + directory_bytes > self.max_directory_bytes):
                    _, (old, _) = self.entries.popitem(last=False)
                    old.close()
                archive = zipfile.ZipFile(path)
                after = path.stat()
                if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != key[1:6]:
                    archive.close()
                    raise ValueError('ZIP changed while opening verified source')
                self.entries[key] = (archive, directory_bytes)
            self.entries.move_to_end(key)
            archive, _ = self.entries[key]
            info = archive.getinfo(member)
            if info.is_dir() or info.file_size < 1 or info.file_size > max_bytes:
                raise ValueError('ZIP asset absent or exceeds remaining byte budget')
            return archive.read(info)  # Includes decompression bounds and ZIP CRC verification.


LOCAL_ZIP_MEMBERS = ZipMemberCache()
