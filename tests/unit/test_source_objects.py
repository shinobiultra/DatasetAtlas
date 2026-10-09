import hashlib
import pytest
from dataset_atlas.storage.sources import register_source,source_object


def test_registered_source_survives_original_removal_and_rejects_drift(tmp_path):
    path=tmp_path/'original';payload=b'real file fixture';path.write_bytes(payload);sha=hashlib.sha256(payload).hexdigest()
    result=register_source(tmp_path,path,sha,100)
    assert not result['reused']
    assert register_source(tmp_path,path,sha,100)['reused']
    path.unlink();cached=source_object(tmp_path,sha,len(payload));assert cached.read_bytes()==payload
    cached.write_bytes(b'x'*len(payload))
    with pytest.raises(ValueError,match='checksum'):source_object(tmp_path,sha,len(payload))


def test_import_budget_checksum_and_symlink_fail_without_registering(tmp_path):
    path=tmp_path/'original';path.write_bytes(b'abc');sha=hashlib.sha256(b'abc').hexdigest()
    with pytest.raises(ValueError,match='budget'):register_source(tmp_path,path,sha,2)
    with pytest.raises(ValueError,match='checksum'):register_source(tmp_path,path,'a'*64,100)
    link=tmp_path/'link';link.symlink_to(path)
    with pytest.raises(OSError):register_source(tmp_path,link,sha,100)
    assert not list((tmp_path/'work/source-objects').iterdir())
