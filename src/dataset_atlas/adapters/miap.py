"""MIAP native annotations with bounded original Open Images reads."""
import hashlib
import io
import re

from PIL import Image

from .core import StructuredAdapter,MediaHandle
from dataset_atlas.storage import BoundedCache,CacheIdentity,HttpsFetcher


class MIAPAdapter(StructuredAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        self.bytes_fetched=0
        self.preparation_transfer_limit: int | None=None

    def _record(self,row,ordinal):
        record=super()._record(row,ordinal)
        for asset in record.assets:
            asset.metadata.update(representation='original Open Images JPEG',
                source_integrity='Native image key; bytes are hashed on access. Unfetched images have not been verified.')
        return record

    def resolve_asset(self,source,asset_ref):
        if not re.fullmatch(r'(train|validation|test)/[a-f0-9]{16}\.jpg',asset_ref):
            raise ValueError('Invalid native MIAP image reference')
        limit=min(source.max_bytes-source.bytes_read,self.config.get('media_transfer_bytes',25_000_000))
        cache=BoundedCache(self.config['remote_cache_root'],self.config.get('remote_cache_bytes',200_000_000))
        url='https://open-images-dataset.s3.amazonaws.com/'+asset_ref
        identity=CacheIdentity(self.revision,hashlib.sha256(url.encode()).hexdigest(),'miap-original')
        cached=cache.get(identity)
        if not cached and self.preparation_transfer_limit is not None:
            limit=min(limit,self.preparation_transfer_limit-self.bytes_fetched)
        if limit<=0:raise ValueError('Original media transfer budget exhausted')
        path=HttpsFetcher(['open-images-dataset.s3.amazonaws.com'],max_bytes=limit).fetch(
            url,cache,identity,byte_budget=limit)
        data=path.read_bytes()
        if not cached:self.bytes_fetched+=len(data)
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>50_000_000:raise ValueError('MIAP image exceeds pixel budget')
            image.verify()
        source.charge(len(data))
        return MediaHandle(data,'image/jpeg',hashlib.sha256(data).hexdigest(),asset_ref)
