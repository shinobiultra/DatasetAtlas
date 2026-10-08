"""Publisher metadata-pinned full-resolution FFHQ PNG access."""
import hashlib,io,re
from PIL import Image
from .core import StructuredAdapter,MediaHandle
from dataset_atlas.storage import BoundedCache,CacheIdentity,HttpsFetcher


class FFHQAdapter(StructuredAdapter):
    def __init__(self,dataset):
        super().__init__(dataset);self.bytes_fetched=0;self.preparation_transfer_limit=None

    def _record(self,row,ordinal):
        record=super()._record(row,ordinal)
        for asset in record.assets:
            asset.metadata.update(native_file_path=row['native_image_path'],native_file_md5=row['native_file_md5'],
                native_pixel_md5=row['native_pixel_md5'],native_image_bytes=row['native_image_bytes'],
                representation='original publisher-aligned 1024×1024 PNG',
                source_integrity='On access: native file MD5, decoded pixel MD5 and size; SHA-256 of the retained original. Unfetched originals remain unverified.')
        return record

    def resolve_asset(self,source,asset_ref):
        match=re.fullmatch(r'drive/([A-Za-z0-9_-]{1,128})/([a-f0-9]{32})/([a-f0-9]{32})/([0-9]{1,7})\.png',asset_ref)
        if not match:raise ValueError('Invalid pinned FFHQ original reference')
        identity,md5,pixels,size=match.groups();size=int(size)
        if not 1<=size<=5_000_000:raise ValueError('FFHQ original exceeds source byte bound')
        limit=min(source.max_bytes-source.bytes_read,self.config.get('media_transfer_bytes',5_000_000))
        cache=BoundedCache(self.config['remote_cache_root'],self.config.get('remote_cache_bytes',300_000_000))
        token=CacheIdentity(self.revision,hashlib.sha256(asset_ref.encode()).hexdigest(),'ffhq-native-png-v1')
        cached=cache.get(token)
        if not cached and self.preparation_transfer_limit is not None:limit=min(limit,self.preparation_transfer_limit-self.bytes_fetched)
        if size>limit:raise ValueError('FFHQ original transfer budget exhausted')
        url=f'https://drive.usercontent.google.com/download?id={identity}&export=download&confirm=t'
        fetcher=HttpsFetcher(['drive.usercontent.google.com'],max_bytes=size,timeout=30)
        try:
            path=fetcher.fetch(url,cache,token,byte_budget=size,cancel=getattr(self,'cancel',None))
        finally:
            self.bytes_fetched+=fetcher.bytes_fetched
        data=path.read_bytes()
        if len(data)!=size or hashlib.md5(data).hexdigest()!=md5:raise ValueError('FFHQ original differs from publisher file MD5/size')
        with Image.open(io.BytesIO(data)) as image:
            if image.format!='PNG' or image.size!=(1024,1024):raise ValueError('FFHQ native PNG dimensions/format changed')
            image.load()
            if hashlib.md5(image.tobytes()).hexdigest()!=pixels:raise ValueError('FFHQ decoded pixels differ from native publisher checksum')
        source.charge(len(data))
        return MediaHandle(data,'image/png',hashlib.sha256(data).hexdigest(),asset_ref)
