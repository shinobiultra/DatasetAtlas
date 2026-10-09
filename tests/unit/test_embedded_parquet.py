import hashlib,io
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from PIL import Image
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.embedded_parquet import EmbeddedParquetAdapter

def fixture(tmp_path):
    stream=io.BytesIO();Image.new('RGB',(3,2),'red').save(stream,format='PNG');data=stream.getvalue()
    rows=[{'id':str(i),'question':'Which colour?','image':{'bytes':data if i!=18 else None,'path':'upstream.png'}} for i in range(40)]
    path=tmp_path/'source.parquet';pq.write_table(pa.Table.from_pylist(rows),path,row_group_size=20)
    dataset=Dataset(id='embedded',name='Fixture',release='r1',snapshot_id='s1',adapter='embedded_parquet',adapter_config={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'mapping':{'id':'id','question':'question','media':'image'}})
    return EmbeddedParquetAdapter(dataset),data

def test_selective_row_access_identity_and_original_bytes(tmp_path):
    adapter,data=fixture(tmp_path);source=adapter.prepare(adapter.plan(10,1_000_000))
    batch=adapter.iter_records(source,'17',4)
    assert [row.source['id'] for row in batch.records]==['17','18','19','20']
    assert batch.next_cursor=='21'
    first=batch.records[0]
    assert first.question=='Which colour?'
    assert first.assets[0].sha256==hashlib.sha256(data).hexdigest()
    assert first.source['image']['source_path']=='upstream.png'
    assert 'bytes' not in first.model_dump_json() or first.source['image']['bytes']==len(data)
    assert batch.records[1].assets[0].uri is None
    assert batch.records[1].assets[0].metadata['status']=='missing_embedded_bytes'
    assert first.asset_ids==batch.records[-1].asset_ids  # same original image, distinct questions
    resolved=adapter.resolve_asset(source,first.assets[0].uri)
    assert resolved.data==data and resolved.media_type=='image/png'
    assert len(adapter.iter_records(source,'39',4).records)==1

def test_unsafe_refs_changed_sources_and_budget_rejected(tmp_path):
    adapter,_=fixture(tmp_path)
    source=adapter.prepare(adapter.plan(10,1_000_000))
    for path in ('../outside.png','embedded/-1/0.png','embedded/0/99.png','embedded/0/0.jpg'):
        with pytest.raises((ValueError,FileNotFoundError)):adapter.resolve_asset(source,path)
    with pytest.raises(ValueError,match='byte budget'):
        adapter.iter_records(adapter.prepare(adapter.plan(1,1)),limit=1)
    adapter._path().write_bytes(b'changed')
    with pytest.raises(ValueError,match='checksum'):adapter.prepare(adapter.plan(1,1000))


@pytest.mark.parametrize('encoding', ['PNG', 'AVIF'])
def test_base64_image_decoding_preserves_original_bytes(tmp_path,encoding):
    import base64
    from dataset_atlas.adapters.columnar import ColumnarAdapter
    stream=io.BytesIO();Image.new('RGB',(3,2),'red').save(stream,format=encoding);data=stream.getvalue()
    path=tmp_path/'encoded.parquet';pq.write_table(pa.table({'image':[base64.b64encode(data).decode()]}),path)
    dataset=Dataset(id='encoded',name='Encoded',release='r',snapshot_id='s',adapter='columnar',adapter_config={
        'files':[{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}],
        'media_columns':['image'],'media_encoding':'base64'})
    adapter=ColumnarAdapter(dataset);source=adapter.prepare(adapter.plan(1,10000));row=adapter.iter_records(source).records[0]
    assert row.source['image']['source_encoding']=='base64'
    assert adapter.source_field_types()['image']=='object'
    assert adapter.resolve_asset(source,row.assets[0].uri).data==data
    with pytest.raises(ValueError):adapter._entries({'image':'not valid base64!'})
