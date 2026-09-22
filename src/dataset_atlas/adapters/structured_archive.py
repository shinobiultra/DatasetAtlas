"""Reusable pinned metadata-to-original-archive media join."""
from functools import lru_cache
import hashlib
from pathlib import Path
import re
from .core import StructuredAdapter,DirectoryArchiveAdapter

@lru_cache(maxsize=64)
def _verify_archive(path,digest,fingerprint):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    if value.hexdigest()!=digest:raise ValueError('Media archive checksum differs from pinned source')

class StructuredArchiveAdapter(StructuredAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        self.archive_path=Path(self.config['media_archive'])
        digest=self.config.get('media_archive_sha256','')
        if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Media archive requires SHA-256 pin')
        media_dataset=dataset.model_copy(update={'adapter_config':{'path':str(self.archive_path),'sha256':digest}})
        self.archive=DirectoryArchiveAdapter(media_dataset)

    def prepare(self,approved_plan):
        source=super().prepare(approved_plan)
        if self.archive_path.is_symlink() or not self.archive_path.is_file():raise ValueError('Media archive is unavailable or linked')
        stat=self.archive_path.stat()
        _verify_archive(str(self.archive_path.resolve()),self.config['media_archive_sha256'],(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns))
        return source

    def resolve_asset(self,source,asset_ref):
        return self.archive.resolve_asset(source,asset_ref)
