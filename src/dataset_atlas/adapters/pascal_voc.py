"""Native VOC annotations and byte-exact original JPEG/palette mask retrieval."""
import hashlib
import json
from pathlib import Path
import sqlite3

from .core import DatasetAdapter, MediaHandle, StructuredAdapter, _safe_relative
from dataset_atlas.storage import BoundedCache
from dataset_atlas.storage.indexed_tar import read_tar_member


class PascalVOCAdapter(StructuredAdapter):
    def __init__(self,dataset):
        super().__init__(dataset);self.bytes_fetched=0;self.preparation_transfer_limit=None

    def prepare_media(self,approved_plan):return DatasetAdapter.prepare(self,approved_plan)

    def _record(self,row,ordinal):
        record=super()._record(row,ordinal)
        if not hasattr(self,'_native_members'):
            index=Path(self.config['original_access_index'])
            proof=json.loads((index/'receipt.json').read_text())
            if proof['source_sha256']!=self.config['native_archive_sha256']:
                raise ValueError('Native VOC retrieval index identifies another source')
            for name,sha in proof['checksums'].items():
                with (index/name).open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=sha:raise ValueError('Native VOC retrieval index checksum changed')
            with sqlite3.connect((index/'members.sqlite').as_uri()+'?mode=ro',uri=True) as db:
                self._native_members=dict(db.execute('SELECT name,sha256 FROM members'))
        for asset in record.assets:
            uri=asset.uri
            if not uri or uri not in self._native_members:raise ValueError('Native VOC asset has no original archive member')
            asset.sha256=self._native_members[uri]
            if '/SegmentationClass/' in uri:asset.metadata['role']='native class segmentation mask'
            elif '/SegmentationObject/' in uri:asset.metadata['role']='native object segmentation mask'
        return record

    def resolve_asset(self,source,asset_ref):
        member=_safe_relative(asset_ref)
        transfer=self.config.get('media_transfer_bytes',200_000_000)
        if self.preparation_transfer_limit is not None:transfer=min(transfer,self.preparation_transfer_limit)
        remaining=transfer-self.bytes_fetched
        if remaining<1:raise ValueError('Native VOC media exceeds its aggregate transfer budget')
        cache=BoundedCache(self.config.get('remote_cache_root','work/media-cache/pascal-voc'),self.config.get('remote_cache_bytes',100_000_000))
        original=self.config.get('original_archive_path');original=Path(original) if original else None
        data,proof=read_tar_member(self.config['original_access_index'],member,local_source=original if original and original.is_file() else None,
            max_bytes=min(source.max_bytes-source.bytes_read,32_000_000),transfer_bytes=remaining,cache=cache)
        source.charge(len(data));self.bytes_fetched+=proof['transferred_bytes']
        return MediaHandle(data,'image/png' if member.endswith('.png') else 'image/jpeg',hashlib.sha256(data).hexdigest(),member)
