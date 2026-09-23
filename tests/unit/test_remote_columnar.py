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
