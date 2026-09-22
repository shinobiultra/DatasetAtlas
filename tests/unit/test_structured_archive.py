import hashlib,json,zipfile
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.structured_archive import StructuredArchiveAdapter

def test_metadata_join_preserves_fields_and_resolves_exact_member(tmp_path):
    archive=tmp_path/'images.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('original/a.png',b'original bytes')
    metadata=tmp_path/'records.json';metadata.write_text(json.dumps([{'id':'q1','image':'original/a.png','answer':'source label'},{'id':'q2','image':'original/a.png','answer':None}]))
    dataset=Dataset(id='joined',name='Joined',release='r1',snapshot_id='s1',adapter='structured_archive',adapter_config={'path':str(metadata),'sha256':hashlib.sha256(metadata.read_bytes()).hexdigest(),'media_archive':str(archive),'media_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'mapping':{'id':'id','media':'image'}})
    adapter=StructuredArchiveAdapter(dataset);source=adapter.prepare(adapter.plan(2,1000))
    rows=adapter.iter_records(source).records
    assert rows[0].asset_ids==rows[1].asset_ids and rows[0].id!=rows[1].id
    assert rows[0].source['answer']=='source label' and rows[1].source['answer'] is None
    assert adapter.resolve_asset(source,rows[0].assets[0].uri).data==b'original bytes'
    with pytest.raises(ValueError):adapter.resolve_asset(source,'../outside.png')
    with pytest.raises((KeyError,FileNotFoundError)):adapter.resolve_asset(source,'absent.png')
    archive.write_bytes(b'changed source')
    with pytest.raises(ValueError,match='checksum'):adapter.prepare(adapter.plan(2,1000))
