"""Native 1.0 UID annotations and bounded original GLB object access."""
import hashlib
import re

from .core import StructuredAdapter,MediaHandle
from .remote_columnar import MediaLimitError
from dataset_atlas.storage import BoundedCache,CacheIdentity,HttpsFetcher
from dataset_atlas.storage.glb import verify_glb
from dataset_atlas.models import stable_id


class ObjaverseAdapter(StructuredAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        self.bytes_fetched=0
        self.preparation_transfer_limit: int | None=None

    def _record(self,row,ordinal):
        record=super()._record(row,ordinal)
        uid=row.get('source_id')
        if not isinstance(uid,str) or not re.fullmatch(r'[A-Za-z0-9]{16,64}',uid):
            raise ValueError('Invalid native Objaverse UID')
        record.unit='entity'
        record.id=stable_id(self.dataset.id,self.revision,'entity',uid)
        return record

    def resolve_asset(self,source,asset_ref):
        if not re.fullmatch(r'glbs/[0-9]{3}-[0-9]{3}/[A-Za-z0-9]{16,64}\.glb',asset_ref):
            raise ValueError('Invalid native Objaverse object path')
        limit=min(source.max_bytes-source.bytes_read,32_000_000)
        if self.preparation_transfer_limit is not None:limit=min(limit,self.preparation_transfer_limit-self.bytes_fetched)
        if limit<1:raise ValueError('Native Objaverse aggregate transfer budget exhausted')
        cache=BoundedCache(self.config['remote_cache_root'],self.config.get('remote_cache_bytes',200_000_000))
        url='https://huggingface.co/datasets/allenai/objaverse/resolve/'+self.config['object_revision']+'/'+asset_ref
        fetcher=HttpsFetcher(['huggingface.co','cdn-lfs-us-1.huggingface.co','us.aws.cdn.hf.co','cas-bridge.xethub.hf.co'],max_bytes=limit)
        try:
            try:path=fetcher.fetch(url,cache,CacheIdentity(self.config['object_revision'],asset_ref,'original'),byte_budget=limit)
            except ValueError as error:
                if 'budget' in str(error):raise MediaLimitError('GLB exceeds the bounded preview transfer limit') from error
                raise
        finally:self.bytes_fetched+=fetcher.bytes_fetched
        data=path.read_bytes()
        try:verify_glb(data)
        except (ValueError,OSError) as error:raise MediaLimitError(str(error)) from error
        source.charge(len(data))
        return MediaHandle(data,'model/gltf-binary',hashlib.sha256(data).hexdigest(),asset_ref)
