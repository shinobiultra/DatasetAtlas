import io,hashlib
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.remote_columnar import RemoteColumnarAdapter


def fixture(tmp_path,monkeypatch):
    import random
    out=io.BytesIO();Image.frombytes('RGB',(300,300),random.Random(42).randbytes(270000)).save(out,'PNG');image=out.getvalue()
    rows=[{'question':f'q{i}','label':i,'images':[{'bytes':image,'path':f'image-{i}.png'},{'bytes':image,'path':f'other-{i}.png'}]} for i in range(8)]
    path=tmp_path/'images.parquet';pq.write_table(pa.Table.from_pylist(rows),path,row_group_size=2,compression='NONE',use_dictionary=False)
    calls=[]
    class Reader(io.BytesIO):
        def __init__(self,*args,**kwargs):super().__init__(path.read_bytes());self.bytes_fetched=0;self.size=path.stat().st_size
        def read(self,n=-1):
            data=super().read(n);self.bytes_fetched+=len(data);calls.append((self.tell()-len(data),len(data)));return data
    monkeypatch.setattr('dataset_atlas.adapters.remote_columnar.HttpsRangeReader',Reader)
    dataset=Dataset(id='remote',name='Fixture',release='r',snapshot_id='s',adapter='remote_columnar',adapter_config={
        'remote_files':[{'url':'https://example.org/images.parquet','source_name':'train/images.parquet','bytes':path.stat().st_size,'etag':'"v1"','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}],
        'remote_cache_root':str(tmp_path/'cache'),'allowed_hosts':['example.org'],'metadata_transfer_bytes':2_000_000})
    return RemoteColumnarAdapter(dataset),image,calls,path


def test_selective_index_keeps_every_row_and_defers_images(tmp_path,monkeypatch):
    adapter,image,calls,path=fixture(tmp_path,monkeypatch)
    source=adapter.prepare(adapter.plan(3,1000000));first=adapter.iter_records(source);late=adapter.iter_records(source,'7')
    assert adapter.count==8 and late.next_cursor is None
    assert [r.source['label'] for r in first.records]==[0,1,2]
    record=late.records[0];assert record.source['label']==7 and len(record.assets)==2
    assert sum(n for _,n in calls)<path.stat().st_size//4
    assert record.assets[0].sha256 is None
    assert adapter.resolve_asset(source,record.assets[1].uri).data==image
    assert adapter.iter_records(source,'7').records[0].id==record.id
    with pytest.raises(ValueError,match='outside'):adapter.resolve_asset(source,'remote/0/800/images/0.png')


def test_selective_media_rowgroup_budget(tmp_path,monkeypatch):
    adapter,_,_,_=fixture(tmp_path,monkeypatch)
    adapter.config['media_transfer_bytes']=100
    source=adapter.prepare(adapter.plan(1,100000))
    record=adapter.iter_records(source).records[0]
    with pytest.raises(ValueError,match='row group'):adapter.resolve_asset(source,record.assets[0].uri)


def test_native_qa_pairs_and_configuration_are_preserved(tmp_path,monkeypatch):
    adapter,_,_,_=fixture(tmp_path,monkeypatch)
    adapter.config['mapping']={'conversation_pairs':'texts','configuration_from_path':True}
    pairs=[{'user':'first','assistant':'one','source':'native'}, {'user':'second','assistant':'two','source':'other'}]
    record=adapter._source_record({'texts':pairs},0,0)
    assert record.source['texts']==pairs
    assert record.source['_atlas_configuration']=='train'
    assert record.question=='first'
    assert record.conversation==[{'role':'user','content':'first'},{'role':'assistant','content':'one'},
                                 {'role':'user','content':'second'},{'role':'assistant','content':'two'}]
    assert adapter.source_field_types()['_atlas_configuration']=='string'
    with pytest.raises(ValueError,match='user/assistant'):
        adapter._source_record({'texts':[{'user':'unanswered'}]},0,1)


def test_parallel_footers_share_one_transfer_cap(tmp_path,monkeypatch):
    adapter,_,_,_=fixture(tmp_path,monkeypatch)
    original=adapter.files[0]
    adapter.files=[{**original,'source_name':f'part-{i}.parquet'} for i in range(4)]
    updates=[]
    adapter.warm_layouts(progress=lambda **x:updates.append(x),workers=2)
    assert adapter.count==32 and len(adapter._layouts)==4
    assert 0 < adapter.bytes_fetched <= adapter.transfer_limit
    assert updates[-1]['schema_shards']==4
    spent=adapter.bytes_fetched
    adapter.warm_layouts()
    assert adapter.bytes_fetched==spent
    adapter._layouts={};adapter.bytes_fetched=0;adapter.transfer_limit=1
    with pytest.raises(ValueError,match='budget'):
        adapter.warm_layouts(workers=2)


def test_parallel_shards_preserve_record_and_asset_identity(tmp_path,monkeypatch):
    adapter,_,_,_=fixture(tmp_path,monkeypatch)
    original=adapter.files[0]
    adapter.files=[{**original,'source_name':f'part-{i}.parquet'} for i in range(4)]
    adapter.config['remote_files']=adapter.files
    adapter.transfer_limit=20_000_000
    source=adapter.prepare(adapter.plan(100,2_000_000))
    expected=adapter.iter_records(source).records
    source=adapter.prepare(adapter.plan(100,2_000_000))
    actual=list(adapter.iter_all_records(source,workers=2))
    assert [r.model_dump() for r in actual]==[r.model_dump() for r in expected]
    assert len({asset.id for row in actual for asset in row.assets})==64
    source=adapter.prepare(adapter.plan(1,10))
    with pytest.raises(ValueError,match='budget'):
        list(adapter.iter_all_records(source,workers=2))


def test_parallel_prefetch_splits_large_batches_without_losing_records(tmp_path,monkeypatch):
    adapter,_,_,path=fixture(tmp_path,monkeypatch)
    pq.write_table(pa.table({'text':['é'*300_000]*30}),path,row_group_size=30)
    adapter.files[0]['bytes']=path.stat().st_size
    adapter.files[0]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    adapter.transfer_limit=100_000_000
    adapter.config['metadata_transfer_bytes']=100_000_000
    source=adapter.prepare(adapter.plan(1000,100_000_000))
    records=list(adapter.iter_all_records(source,workers=1))
    assert len(records)==30 and len({r.id for r in records})==30
    assert all(r.text=='é'*300_000 and r.source['text']==r.text for r in records)
    assert 32_000_000 < source.bytes_read < 100_000_000


def test_closing_parallel_iterator_releases_producers(tmp_path,monkeypatch):
    import threading
    adapter,_,_,_=fixture(tmp_path,monkeypatch)
    original=adapter.files[0]
    adapter.files=[{**original,'source_name':f'part-{i}.parquet'} for i in range(4)]
    adapter.config['remote_files']=adapter.files;adapter.transfer_limit=20_000_000
    source=adapter.prepare(adapter.plan(100,2_000_000))
    before=set(threading.enumerate());stream=adapter.iter_all_records(source,workers=2)
    next(stream)
    threads=set(threading.enumerate())-before
    assert threads
    stream.close()
    assert not any(thread.is_alive() for thread in threads)


def test_binary_lists_preserve_order_nulls_and_original_bytes(tmp_path,monkeypatch):
    adapter,image,_,path=fixture(tmp_path,monkeypatch)
    pq.write_table(pa.table({'question':['paired','absent','single'],
                            'image':[[image,None,image],None,[image]]}),path,row_group_size=3)
    adapter.files[0]['bytes']=path.stat().st_size
    adapter.files[0]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    adapter.config['media_columns']=['image']
    source=adapter.prepare(adapter.plan(3,10_000_000))
    records=adapter.iter_records(source).records
    assert len(records[0].assets)==2 and records[0].source['image'][1] is None
    assert not records[1].assets and len(records[2].assets)==1
    assert records[0].assets[1].metadata['source_slot']==2
    assert adapter.resolve_asset(source,records[0].assets[1].uri).data==image
    assert adapter.media_bytes_fetched>0
    # The group is larger than the decoded-batch cap, but its small batches fit.
    adapter.config['media_decode_bytes']=10
    from dataset_atlas.adapters.remote_columnar import MediaLimitError
    with pytest.raises(MediaLimitError,match='batch'):
        adapter.resolve_asset(source,records[0].assets[0].uri)


def test_media_network_bytes_share_preparation_transfer_limit(tmp_path,monkeypatch):
    adapter,_,calls,_=fixture(tmp_path,monkeypatch)
    source=adapter.prepare(adapter.plan(1,1_000_000))
    record=adapter.iter_records(source).records[0]
    adapter.resolve_asset(source,record.assets[0].uri)
    assert adapter.bytes_fetched+adapter.media_bytes_fetched==sum(count for _,count in calls)
    adapter.config['aggregate_transfer_bytes']=adapter.bytes_fetched+adapter.media_bytes_fetched
    before=len(calls)
    with pytest.raises(ValueError,match='budget exhausted'):
        adapter.resolve_asset(source,record.assets[0].uri)
    assert len(calls)==before
