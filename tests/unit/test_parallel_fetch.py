import hashlib
import io
import json

import pytest

from dataset_atlas.storage import BoundedCache,CacheIdentity
from dataset_atlas.storage.parallel_fetch import fetch_checksum_ranges


def fake_transport(monkeypatch,payload,*,status=206,mutate=False):
    class Connection:
        def __init__(self,*args):pass
        def request(self,method,target,headers):self.start,self.end=map(int,headers['Range'][6:].split('-'))
        def getresponse(self):
            data=payload[self.start:self.end+1]
            if mutate:data=bytes([data[0]^1])+data[1:]
            response=io.BytesIO(data);response.status=status
            headers={'Content-Length':str(len(data)),'Content-Range':f'bytes {self.start}-{self.end}/{len(payload)}'}
            response.getheader=lambda key,default=None:headers.get(key,default)
            return response
        def close(self):pass
    monkeypatch.setattr('dataset_atlas.storage.parallel_fetch._PinnedHTTPSConnection',Connection)
    monkeypatch.setattr('dataset_atlas.storage.https.HttpsFetcher._destination',lambda self,url:('example.org',443,'93.184.216.34','/source'))


def fixture(tmp_path,monkeypatch,**kwargs):
    payload=b'native publisher bytes'+bytes(range(256))*50;fake_transport(monkeypatch,payload,**kwargs)
    cache=BoundedCache(tmp_path/'cache',len(payload));identity=CacheIdentity('fixture','native','original')
    entry={'bytes':len(payload),'url':'https://example.org/native','md5':hashlib.md5(payload).hexdigest()}
    return payload,entry,cache,identity


def test_parallel_native_acquisition_reuses_unverified_prefix_only_after_full_checksum(tmp_path,monkeypatch):
    payload,entry,cache,identity=fixture(tmp_path,monkeypatch)
    part=cache.partial_path(identity);part.write_bytes(payload[:1234]);part.with_suffix('.json').write_text(json.dumps({'url':entry['url'],'total_bytes':len(payload)}))
    target,proof=fetch_checksum_ranges(entry,cache,identity,allowed_hosts=['example.org'],byte_budget=len(payload),chunk_bytes=1000)
    assert target.read_bytes()==payload and proof['network_bytes']==len(payload) and proof['reused_prefix_bytes']==1234
    assert cache.get(identity)==target


@pytest.mark.parametrize('status,mutate,match',[(200,False,'HTTP 206'),(206,True,'publisher checksum')])
def test_failed_native_ranges_are_never_exposed_as_originals(tmp_path,monkeypatch,status,mutate,match):
    payload,entry,cache,identity=fixture(tmp_path,monkeypatch,status=status,mutate=mutate)
    with pytest.raises(ValueError,match=match):
        fetch_checksum_ranges(entry,cache,identity,allowed_hosts=['example.org'],byte_budget=len(payload),chunk_bytes=1000)
    assert cache.get(identity) is None
    assert cache.partial_path(identity).with_suffix('.ranges.json').exists()
