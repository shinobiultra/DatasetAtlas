import hashlib,io,json
from pathlib import Path
from PIL import Image
import pytest
from dataset_atlas.converters.ffhq import ffhq_metadata
from dataset_atlas.adapters.ffhq import FFHQAdapter
from dataset_atlas.models import Dataset


def fixture(tmp_path):
    image=Image.new('RGB',(1024,1024),(10,20,30));stream=io.BytesIO();image.save(stream,format='PNG');data=stream.getvalue()
    md5=hashlib.md5(data).hexdigest();pixels=hashlib.md5(image.tobytes()).hexdigest()
    native={'image':{'file_url':'https://drive.google.com/uc?id=synthetic-id','file_path':'fixture.png','file_size':len(data),'pixel_size':[1024,1024],
                     'file_md5':md5,'pixel_md5':pixels,'face_landmarks':[[1.25,2.5]]},'category':'synthetic','metadata':{'license':'fixture-only','extra':['native',None]},
            'thumbnail':{'fixture':True},'in_the_wild':{'fixture':True}}
    path=tmp_path/'metadata.json';path.write_text(json.dumps({'0':native}));return path,native,data


def test_native_metadata_preserves_all_nested_fields_and_checksum_bindings(tmp_path):
    path,native,data=fixture(tmp_path);result=ffhq_metadata({'count':1},{'metadata':path},tmp_path/'out',lambda:None)
    row=json.loads(result['path'].read_text())
    assert json.loads(row['native_metadata_json'])==native and row['source_id']=='0'
    assert row['media_ref'].endswith(f"/{native['image']['file_md5']}/{native['image']['pixel_md5']}/{len(data)}.png")
    assert result['count']==1
    with pytest.raises(ValueError,match='population'):ffhq_metadata({'count':2},{'metadata':path},tmp_path/'bad',lambda:None)


@pytest.mark.parametrize('url',['http://drive.google.com/uc?id=x','https://example.org/uc?id=x','https://drive.google.com/uc?id=x&redirect=evil','https://drive.google.com/uc?id=../../evil'])
def test_native_metadata_cannot_expand_media_hosts_or_paths(tmp_path,url):
    path,native,_=fixture(tmp_path);native['image']['file_url']=url;path.write_text(json.dumps({'0':native}))
    with pytest.raises(ValueError):ffhq_metadata({'count':1},{'metadata':path},tmp_path/'out',lambda:None)


def test_original_png_requires_file_and_decoded_pixel_checksums(tmp_path,monkeypatch):
    path,native,data=fixture(tmp_path);result=ffhq_metadata({'count':1},{'metadata':path},tmp_path/'out',lambda:None)
    original=tmp_path/'native.png';original.write_bytes(data)
    from dataset_atlas.storage import HttpsFetcher
    destinations=[]
    def fetch(self,url,*args,**kwargs):destinations.append(url);return original
    monkeypatch.setattr(HttpsFetcher,'fetch',fetch)
    dataset=Dataset(id='synthetic-ffhq',name='Synthetic',release='fixture',snapshot_id='fixture',adapter='ffhq',
      adapter_config={'path':str(result['path']),'format':'jsonl','mapping':{'id':'source_id','media':'media_ref'},'remote_cache_root':str(tmp_path/'cache')})
    adapter=FFHQAdapter(dataset);source=adapter.prepare(adapter.plan(1,100_000));row=json.loads(result['path'].read_text())
    handle=adapter.resolve_asset(source,row['media_ref']);assert handle.data==data
    assert destinations==['https://drive.usercontent.google.com/download?id=synthetic-id&export=download&confirm=t']
    with pytest.raises(ValueError,match='decoded pixels'):
        adapter.resolve_asset(adapter.prepare(adapter.plan(1,100_000)),row['media_ref'].replace(native['image']['pixel_md5'],'0'*32))
    with pytest.raises(ValueError,match='Invalid pinned'):
        adapter.resolve_asset(source,'../../evil.png')


def test_failed_native_transfer_is_charged_before_another_attempt(tmp_path,monkeypatch):
    path,_,data=fixture(tmp_path);result=ffhq_metadata({'count':1},{'metadata':path},tmp_path/'out',lambda:None)
    from dataset_atlas.storage import HttpsFetcher
    calls=[]
    def fetch(self,*args,**kwargs):
        calls.append(True);self.bytes_fetched=len(data)-1
        raise ValueError('synthetic truncated transfer')
    monkeypatch.setattr(HttpsFetcher,'fetch',fetch)
    dataset=Dataset(id='synthetic-ffhq',name='Synthetic',release='fixture',snapshot_id='fixture',adapter='ffhq',
      adapter_config={'path':str(result['path']),'format':'jsonl','mapping':{'id':'source_id','media':'media_ref'},'remote_cache_root':str(tmp_path/'cache')})
    adapter=FFHQAdapter(dataset);adapter.preparation_transfer_limit=len(data)+1
    source=adapter.prepare(adapter.plan(1,100_000));ref=json.loads(result['path'].read_text())['media_ref']
    with pytest.raises(ValueError,match='truncated'):adapter.resolve_asset(source,ref)
    assert adapter.bytes_fetched==len(data)-1
    with pytest.raises(ValueError,match='budget'):adapter.resolve_asset(source,ref)
    assert len(calls)==1
