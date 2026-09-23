"""Reuse remote ZIP directories while giving each media read its own stream."""

from collections import OrderedDict
import hashlib
import json
import threading
import zipfile


class _DirectoryZipFile(zipfile.ZipFile):
    def __init__(self, source, directory):
        self._directory = directory
        super().__init__(source, "r")

    def _RealGetContents(self):
        # zipfile still checks local headers, names, overlap, lengths and CRCs.
        # Only its already-validated central-directory parse is reused.
        self.filelist, self.NameToInfo, self.start_dir, self._comment = self._directory


class RemoteZipMemberCache:
    def __init__(self, max_archives=4, max_directory_bytes=100_000_000):
        self.max_archives = max_archives
        self.max_directory_bytes = max_directory_bytes
        self.entries = OrderedDict()
        self.lock = threading.RLock()

    def read(self, source, spec, member, max_bytes):
        from dataset_atlas.adapters.core import _safe_relative

        member = _safe_relative(member)
        key = hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with self.lock:
            if key not in self.entries:
                end = zipfile._EndRecData(source)  # ty: ignore[unresolved-attribute]
                if end is None:
                    raise ValueError("Invalid remote ZIP archive")
                size = end[zipfile._ECD_SIZE]  # ty: ignore[unresolved-attribute]
                if (
                    size > self.max_directory_bytes
                    or end[zipfile._ECD_ENTRIES_TOTAL] > 1_000_000  # ty: ignore[unresolved-attribute]
                ):
                    raise ValueError("Remote ZIP directory exceeds metadata budget")
                with zipfile.ZipFile(source) as archive:
                    if len(archive.filelist) != len(archive.NameToInfo):
                        raise ValueError("Remote ZIP has duplicate native member names")
                    directory = (
                        archive.filelist,
                        archive.NameToInfo,
                        archive.start_dir,
                        archive.comment,
                    )
                while self.entries and (
                    len(self.entries) >= self.max_archives
                    or sum(value[1] for value in self.entries.values()) + size
                    > self.max_directory_bytes
                ):
                    self.entries.popitem(last=False)
                self.entries[key] = (directory, size)
            self.entries.move_to_end(key)
            directory, _ = self.entries[key]
        with _DirectoryZipFile(source, directory) as archive:
            info = archive.getinfo(member)
            if info.is_dir() or not 1 <= info.file_size <= max_bytes:
                raise ValueError("Remote ZIP member exceeds byte budget")
            return archive.read(info)


REMOTE_ZIP_MEMBERS = RemoteZipMemberCache()
