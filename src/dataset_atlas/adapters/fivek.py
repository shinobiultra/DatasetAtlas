"""Native expert TIFF renditions; raw inputs and other conditions stay explicit."""
import hashlib
import io
import re
from urllib.parse import quote

from PIL import Image

from .core import StructuredAdapter,MediaHandle
from dataset_atlas.storage import BoundedCache,CacheIdentity,HttpsFetcher


class FiveKAdapter(StructuredAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        self.bytes_fetched=0
        self.preparation_transfer_limit: int | None=None

    def _record(self,row,ordinal):
        record=super()._record(row,ordinal)
        for asset in record.assets:
            asset.metadata.update(representation='original 16-bit expert TIFF',condition='expert_'+row['expert'],
                source_format='TIFF16',browser_render_required=True,
                source_integrity='Native author file link; bytes are hashed on access. Unfetched renditions have not been verified.',
                raw_input=row['raw_input'],raw_input_availability='DNG input referenced; raw bytes not acquired')
        return record

    def resolve_asset(self,source,asset_ref):
        if not re.fullmatch(r'img/tiff16_[a-e]/a[0-9]{4}-[^/\\\x00-\x1f]+\.tif',asset_ref) or '..' in asset_ref:
            raise ValueError('Invalid native FiveK TIFF reference')
        limit=min(source.max_bytes-source.bytes_read,self.config.get('media_transfer_bytes',150_000_000))
        cache=BoundedCache(self.config['remote_cache_root'],self.config.get('remote_cache_bytes',200_000_000))
        url='https://data.csail.mit.edu/graphics/fivek/'+quote(asset_ref,safe='/')
        identity=CacheIdentity(self.revision,hashlib.sha256(url.encode()).hexdigest(),'fivek-original-tiff')
        cached=cache.get(identity)
        if not cached and self.preparation_transfer_limit is not None:
            limit=min(limit,self.preparation_transfer_limit-self.bytes_fetched)
        if limit<=0:raise ValueError('Original media transfer budget exhausted')
        path=HttpsFetcher(['data.csail.mit.edu'],max_bytes=limit).fetch(url,cache,identity,byte_budget=limit)
        data=path.read_bytes()
        if not cached:self.bytes_fetched+=len(data)
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>50_000_000:raise ValueError('FiveK TIFF exceeds pixel budget')
            image.verify()
        source.charge(len(data))
        return MediaHandle(data,'image/tiff',hashlib.sha256(data).hexdigest(),asset_ref)
