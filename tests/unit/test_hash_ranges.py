import hashlib
import io
from pathlib import Path

import pytest

from dataset_atlas.storage import BoundedCache
from dataset_atlas.storage.hash_ranges import HashPinnedRangeReader,block_manifest


def transport(monkeypatch,payload,*,status=206,alter=False):
    calls=[]
    class Connection:
        def __init__(self,*args):pass
        def request(self,method,target,headers):
            self.start,self.end=map(int,headers['Range'][6:].split('-'));calls.append((self.start,self.end))
        def getresponse(self):
            data=payload[self.start:self.end+1]
            if alter:data=data[:-1]+bytes([data[-1]^1])
            body=io.BytesIO(data);body.status=status
            headers={'Content-Length':str(len(data)),'Content-Range':f'bytes {self.start}-{self.end}/{len(payload)}'}
            body.getheader=lambda key,default=None:headers.get(key,default)
            return body
        def close(self):pass
    monkeypatch.setattr('dataset_atlas.storage.hash_ranges._PinnedHTTPSConnection',Connection)
    monkeypatch.setattr('dataset_atlas.storage.https.HttpsFetcher._destination',lambda self,url:('example.org',443,'93.184.216.34','/source'))
    return calls


def reader(tmp_path,monkeypatch,**kwargs):
    payload=b'0123456789abcdefXYZ';path=tmp_path/'native';path.write_bytes(payload)
    spec=block_manifest(path,block_bytes=8)
    calls=transport(monkeypatch,payload,**kwargs)
    return HashPinnedRangeReader('https://example.org/source',size=spec['bytes'],source_sha256=spec['source_sha256'],
        block_bytes=spec['block_bytes'],block_sha256=spec['block_sha256'],allowed_hosts=['example.org'],byte_budget=19),calls


def test_entire_blocks_verified_and_cached_without_etags(tmp_path,monkeypatch):
    source,calls=reader(tmp_path,monkeypatch);cache=BoundedCache(tmp_path/'cache',100);source.cache=cache
    source.seek(6);assert source.read(5)==b'6789a'
    assert calls==[(0,7),(8,15)] and source.bytes_fetched==16
    source.seek(18);assert source.read(1)==b'Z' and source.bytes_fetched==19
    cold,_=reader(tmp_path,monkeypatch);cold.cache=cache;cold.byte_budget=1;cold.seek(18)
    assert cold.read(1)==b'Z' and cold.bytes_fetched==0


def test_change_outside_requested_slice_is_rejected(tmp_path,monkeypatch):
    source,_=reader(tmp_path,monkeypatch,alter=True)
    with pytest.raises(ValueError,match='SHA-256'):source.read(1)


def test_budget_includes_whole_verified_blocks_and_ignored_range_is_rejected(tmp_path,monkeypatch):
    source,_=reader(tmp_path,monkeypatch);source.byte_budget=7
    with pytest.raises(ValueError,match='transfer budget'):source.read(1)
    source,_=reader(tmp_path,monkeypatch,status=200)
    with pytest.raises(ValueError,match='HTTP 206'):source.read(1)


def test_hash_pinned_gzip_original_reads_survive_retirement(tmp_path,monkeypatch):
    import tarfile
    from dataset_atlas.storage.indexed_tar import build_tar_index,read_tar_member
    path=tmp_path/'native.tar.gz'
    with tarfile.open(path,'w:gz') as archive:
        for name,data in [('first',b'first native bytes'),('last',b'last native bytes')]:
            info=tarfile.TarInfo(name);info.size=len(data);archive.addfile(info,io.BytesIO(data))
    payload=path.read_bytes();spec=block_manifest(path,block_bytes=64);sha=hashlib.sha256(payload).hexdigest()
    remote={'url':'https://example.org/native','allowed_hosts':['example.org'],**spec}
    index=tmp_path/'index';build_tar_index(path,index,source_sha256=sha,remote=remote,max_uncompressed_bytes=20000)
    path.unlink();transport(monkeypatch,payload)
    data,proof=read_tar_member(index,'last',transfer_bytes=10000)
    assert data==b'last native bytes' and proof['fingerprint_type']=='sha256-blocks'
    assert proof['source_sha256']==sha


def test_truncated_blocks_charge_actual_network_bytes_before_retry(tmp_path,monkeypatch):
    source,_=reader(tmp_path,monkeypatch)
    original=__import__('dataset_atlas.storage.hash_ranges',fromlist=['_PinnedHTTPSConnection'])._PinnedHTTPSConnection
    class Truncated(original):
        def getresponse(self):
            response=super().getresponse();response.seek(0);response.truncate(3);return response
    monkeypatch.setattr('dataset_atlas.storage.hash_ranges._PinnedHTTPSConnection',Truncated)
    with pytest.raises(ValueError,match='payload length'):source.read(1)
    assert source.bytes_fetched==3


def test_hash_pinned_zip_member_uses_verified_blocks_and_accounts_failures(tmp_path,monkeypatch):
    import zipfile
    from dataset_atlas.storage.indexed_zip import build_zip_index,read_zip_member
    path=tmp_path/'native.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('native.bin',b'original bytes')
    payload=path.read_bytes();manifest=block_manifest(path,block_bytes=32)
    remote={'url':'https://example.org/native','allowed_hosts':['example.org'],**manifest}
    index=tmp_path/'index';build_zip_index(path,index,source_sha256=manifest['source_sha256'],remote=remote,max_input_bytes=1000)
    path.unlink();transport(monkeypatch,payload);charged=[]
    data,proof=read_zip_member(index,'native.bin',transfer_bytes=1000,on_transfer=charged.append)
    assert data==b'original bytes' and proof['fingerprint_type']=='sha256-blocks' and sum(charged)>0
    transport(monkeypatch,payload,alter=True);charged=[]
    with pytest.raises(ValueError,match='SHA-256'):read_zip_member(index,'native.bin',transfer_bytes=1000,on_transfer=charged.append)
    assert sum(charged)>0


def test_cancelled_hash_range_cache_writer_does_not_wait_for_competing_lock(tmp_path,monkeypatch):
    import fcntl,time
    source,_=reader(tmp_path,monkeypatch);source.cache=BoundedCache(tmp_path/'cache',100)
    start=time.monotonic()
    def cancel():
        if time.monotonic()-start>.05:raise InterruptedError('synthetic cancellation')
    source.cancel=cancel
    with (source.cache.root/'hash-range.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with pytest.raises(InterruptedError,match='cancellation'):source.read(1)
    assert time.monotonic()-start<.5 and source.bytes_fetched==8
