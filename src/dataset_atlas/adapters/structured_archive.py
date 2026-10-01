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
        self.remote=None
        if 'remote_media_archive' in self.config:
            # The media ZIP is too large to download (e.g. COCO val2014, 6.6 GB): read members by ETag-bound ranges.
            from .remote_media import RemoteZip
            self.remote=RemoteZip(self.config['remote_media_archive'],self.config['remote_cache_root'],self.config.get('remote_cache_bytes',1_000_000_000))
            self.archive_path=self.archive=None
            return
        self.archive_path=Path(self.config['media_archive'])
        digest=self.config.get('media_archive_sha256','')
        if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Media archive requires SHA-256 pin')
        media_dataset=dataset.model_copy(update={'adapter_config':{'path':str(self.archive_path),'sha256':digest}})
        self.archive=DirectoryArchiveAdapter(media_dataset)

    def prepare(self,approved_plan):
        source=super().prepare(approved_plan)
        if self.remote:return source
        if self.archive_path.is_symlink() or not self.archive_path.is_file():raise ValueError('Media archive is unavailable or linked')
        stat=self.archive_path.stat()
        _verify_archive(str(self.archive_path.resolve()),self.config['media_archive_sha256'],(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns))
        return source

    def resolve_asset(self,source,asset_ref):
        if self.remote:
            import hashlib as _hashlib
            from .core import MediaHandle,_media_type,_safe_relative
            name=_safe_relative(asset_ref)
            data=self.remote.read(name,source.max_bytes-source.bytes_read,self.config.get('media_transfer_bytes',40_000_000))
            source.charge(len(data))
            return MediaHandle(data,_media_type(name),_hashlib.sha256(data).hexdigest(),name)
        return self.archive.resolve_asset(source,asset_ref)
