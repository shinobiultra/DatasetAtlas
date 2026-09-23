import hashlib
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from dataset_atlas.storage.zip_members import ZipMemberCache


def test_zip_directory_reused_and_evicted_with_bounded_member_reads(tmp_path, monkeypatch):
    paths=[]
    for index in range(3):
        path=tmp_path/f'{index}.zip'
        with zipfile.ZipFile(path,'w') as archive:archive.writestr('image.bin',b'0123456789')
        paths.append(path)
    original=zipfile.ZipFile;opened=[]
    def tracked(*args,**kwargs):
        value=original(*args,**kwargs);opened.append(value);return value
    monkeypatch.setattr(zipfile,'ZipFile',tracked)
    cache=ZipMemberCache(max_archives=2)
    sha=hashlib.sha256(paths[0].read_bytes()).hexdigest()
    with ThreadPoolExecutor(4) as pool:
        assert list(pool.map(lambda _:cache.read(paths[0],'image.bin',10,sha),range(20)))==[b'0123456789']*20
    assert len(opened)==1
    with pytest.raises(ValueError,match='byte budget'):cache.read(paths[0],'image.bin',9,sha)
    with pytest.raises(ValueError):cache.read(paths[0],'../image.bin',10,sha)
    for path in paths[1:]:cache.read(path,'image.bin',10)
    assert len(cache.entries)==2 and opened[0].fp is None
    cache.close();assert not cache.entries and all(archive.fp is None for archive in opened)


def test_changed_zip_cannot_reuse_a_verified_directory(tmp_path):
    path=tmp_path/'a.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr('a',b'first')
    sha=hashlib.sha256(path.read_bytes()).hexdigest();cache=ZipMemberCache()
    assert cache.read(path,'a',100,sha)==b'first'
    with zipfile.ZipFile(path,'w') as z:z.writestr('a',b'changed')
    with pytest.raises(ValueError,match='pinned checksum'):cache.read(path,'a',100,sha)
    with pytest.raises(ValueError,match='metadata budget'):ZipMemberCache(max_directory_bytes=1).read(path,'a',100)
    cache.close()
