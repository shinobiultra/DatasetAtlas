"""Native EmoSet JPEGs retrieved through complete-original SHA-256 block pins."""
import hashlib
import io
from PIL import Image
from .core import StructuredAdapter,MediaHandle,_safe_relative
from dataset_atlas.storage import BoundedCache
from dataset_atlas.storage.indexed_zip import read_zip_member


class EmoSetAdapter(StructuredAdapter):
    def __init__(self,dataset):
        super().__init__(dataset);self.bytes_fetched=0;self.preparation_transfer_limit=None

    def _record(self,row,ordinal):
        record=super()._record(row,ordinal)
        for asset in record.assets:
            asset.metadata.update(representation='original native EmoSet JPEG',native_image_path=row['native_image_path'],
                source_integrity='Whole author-linked archive SHA-256 measured locally; all native members CRC/SHA-256 indexed. Later range blocks and original member SHA-256 checked; no independent publisher digest supplied.')
        return record

    def resolve_asset(self,source,asset_ref):
        member=_safe_relative(asset_ref)
        if not member.endswith('.jpg'):raise ValueError('EmoSet original is not a native JPEG reference')
        limit=self.config.get('media_transfer_bytes',10_000_000)
        if self.preparation_transfer_limit is not None:limit=min(limit,self.preparation_transfer_limit-self.bytes_fetched)
        if limit<1:raise ValueError('EmoSet native transfer budget exhausted')
        cache=BoundedCache(self.config['remote_cache_root'],self.config.get('remote_cache_bytes',200_000_000))
        def charge(count):self.bytes_fetched+=count
        data,proof=read_zip_member(self.config['native_zip_index'],member,max_bytes=min(source.max_bytes-source.bytes_read,10_000_000),
            transfer_bytes=limit,cache=cache,cancel=getattr(self,'cancel',None),on_transfer=charge)
        with Image.open(io.BytesIO(data)) as image:
            if image.format!='JPEG' or image.width*image.height>50_000_000:raise ValueError('Native EmoSet image format/pixels exceed bounds')
            image.load()
        source.charge(len(data))
        return MediaHandle(data,'image/jpeg',proof['sha256'],asset_ref)
