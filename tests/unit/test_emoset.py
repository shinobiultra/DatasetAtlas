import hashlib,io,json,zipfile
from pathlib import Path
from PIL import Image
import pytest
from dataset_atlas.converters.emoset import emoset_native


def native_fixture(tmp_path,*,orphan=False,bad_join=False):
    stream=io.BytesIO();Image.new('RGB',(16,12),'red').save(stream,format='JPEG');image=stream.getvalue()
    native={'image_id':'synthetic-0','emotion':'fixture-emotion','brightness':0.25,'object':['fixture'],'unknown':{'keep':[None,True]}}
    if bad_join:native['image_id']='different'
    path=tmp_path/'native.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('info.json',json.dumps({'label2idx':{'fixture-emotion':0},'idx2label':{'0':'fixture-emotion'}}))
        z.writestr('train.json',json.dumps([['fixture-emotion','image/synthetic-0.jpg','annotation/synthetic-0.json']]))
        for split in ['val','test']:z.writestr(split+'.json','[]')
        z.writestr('image/synthetic-0.jpg',image);z.writestr('annotation/synthetic-0.json',json.dumps(native))
        if orphan:z.writestr('image/orphan.jpg',image)
    params={'count':1,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'url':'https://example.org/native.zip','allowed_hosts':['example.org'],'max_input_bytes':100_000}
    return path,params,native,image


def test_full_native_membership_preserves_unknown_annotation_and_split_values(tmp_path):
    path,params,native,_=native_fixture(tmp_path)
    result=emoset_native(params,{'archive':path},tmp_path/'out',lambda:None)
    row=json.loads(result['path'].read_text())
    assert json.loads(row['native_annotation_json'])==native
    assert row['attribute_unknown']==native['unknown'] and row['split']=='train' and row['split_ordinal']==0
    assert result['native_source_checks']['indexed_members']==6
    assert len(result['derived_sources'])==2


@pytest.mark.parametrize('kwargs',[{'orphan':True},{'bad_join':True}])
def test_native_unjoined_or_missing_population_fails(tmp_path,kwargs):
    path,params,_,_=native_fixture(tmp_path,**kwargs)
    with pytest.raises(ValueError,match='population|join'):
        emoset_native(params,{'archive':path},tmp_path/'out',lambda:None)


def test_original_jpeg_range_blocks_survive_native_source_retirement(tmp_path,monkeypatch):
    from test_hash_ranges import transport
    from dataset_atlas.adapters.emoset import EmoSetAdapter
    from dataset_atlas.models import Dataset
    path,params,_,image=native_fixture(tmp_path);payload=path.read_bytes()
    result=emoset_native(params,{'archive':path},tmp_path/'out',lambda:None)
    path.unlink();transport(monkeypatch,payload)
    dataset=Dataset(id='synthetic-emoset',name='Synthetic',release='fixture',snapshot_id='fixture',adapter='emoset',
       adapter_config={**result['adapter_config'],'path':str(result['path']),'format':'jsonl','remote_cache_root':str(tmp_path/'cache')})
    adapter=EmoSetAdapter(dataset);source=adapter.prepare(adapter.plan(1,100_000))
    media=adapter.resolve_asset(source,'image/synthetic-0.jpg')
    assert media.data==image and media.sha256==hashlib.sha256(image).hexdigest() and adapter.bytes_fetched==len(payload)
    with pytest.raises(ValueError):adapter.resolve_asset(source,'../evil.jpg')


def test_cancel_after_index_completion_can_resume_the_same_owned_output(tmp_path):
    path,params,_,_=native_fixture(tmp_path);out=tmp_path/'out';before=hashlib.sha256(path.read_bytes()).hexdigest()
    def cancel():
        if (out/'native-index/receipt.json').exists():raise InterruptedError('synthetic cancellation after index')
    with pytest.raises(InterruptedError):emoset_native(params,{'archive':path},out,cancel)
    assert (out/'native-index/receipt.json').exists()
    result=emoset_native(params,{'archive':path},out,lambda:None)
    assert result['count']==1 and hashlib.sha256(path.read_bytes()).hexdigest()==before
    with (out/'native-index/members.sqlite').open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='checksum changed'):emoset_native(params,{'archive':path},out,lambda:None)
