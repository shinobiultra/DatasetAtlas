import hashlib
import io
import importlib.util
from pathlib import Path
import shutil

import pytest

from dataset_atlas.storage.cache import BoundedCache,CacheIdentity
from dataset_atlas.storage.legacy import fetch_svhn


def setup(tmp_path,monkeypatch,payload=b'original',status=200,address='93.184.216.34'):
    url='http://ufldl.stanford.edu/housenumbers/train_32x32.mat'
    sha=hashlib.sha256(b'original').hexdigest()
    monkeypatch.setattr('dataset_atlas.storage.legacy.SVHN_FILES',{url:(8,sha)})
    monkeypatch.setattr('dataset_atlas.storage.legacy.HttpsFetcher._resolve',lambda *args:[(None,None,None,None,(address,80))])
    class Response(io.BytesIO):
        def __init__(self):super().__init__(payload);self.status=status
        def getheader(self,key):return str(len(payload)) if key=='Content-Length' else None
    class Connection:
        def __init__(self,*args):pass
        def request(self,*args,**kwargs):pass
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr('dataset_atlas.storage.legacy._PinnedHTTPConnection',Connection)
    return {'url':url,'bytes':8,'sha256':sha},BoundedCache(tmp_path/'cache',100),CacheIdentity('fixture',sha,'original')


def test_only_complete_checksum_matching_file_enters_cache(tmp_path,monkeypatch):
    entry,cache,identity=setup(tmp_path,monkeypatch)
    path=fetch_svhn(entry,cache,identity)
    assert path.read_bytes()==b'original'
    assert fetch_svhn(entry,cache,identity)==path


@pytest.mark.parametrize('payload,status,address,reason',[(b'tampered',200,'93.184.216.34','SHA-256'),(b'original',302,'93.184.216.34','redirects'),(b'original',200,'127.0.0.1','nonpublic'),(b'oversized',200,'93.184.216.34','length')])
def test_bad_integrity_redirects_private_ips_and_lengths_are_rejected(tmp_path,monkeypatch,payload,status,address,reason):
    entry,cache,identity=setup(tmp_path,monkeypatch,payload,status,address)
    with pytest.raises(ValueError,match=reason):fetch_svhn(entry,cache,identity)
    assert cache.usage()['entries']==0 and not cache.partial_path(identity).exists()


def test_an_arbitrary_http_recipe_cannot_use_the_exception(tmp_path,monkeypatch):
    entry,cache,identity=setup(tmp_path,monkeypatch)
    entry['url']='http://example.org/native.mat'
    with pytest.raises(ValueError,match='restricted'):fetch_svhn(entry,cache,identity)


def test_svhn_plan_requires_optional_mat_reader_before_downloading(tmp_path,monkeypatch):
    from dataset_atlas.preparation import PreparationManager
    repository=Path(__file__).resolve().parents[2]
    for category in ('datasets','recipes'):
        destination=tmp_path/'registry'/category
        destination.mkdir(parents=True)
        shutil.copy2(repository/'registry'/category/'svhn.yaml',destination/'svhn.yaml')
    find_spec=importlib.util.find_spec
    monkeypatch.setattr(importlib.util,'find_spec',lambda name:None if name=='scipy' else find_spec(name))
    plan=PreparationManager(tmp_path).plan('svhn',300_000_000,600_000_000)
    assert not plan['ready']
    assert any('dataset-atlas[datasets]' in requirement for requirement in plan['requirements'])
    assert plan['expected_download_bytes']==246_316_178
    assert not (tmp_path/'work/download-cache').exists()
