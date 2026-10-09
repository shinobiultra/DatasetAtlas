"""Synthetic Places annotation/archive joins; no publisher images or labels."""
import hashlib
import io
import tarfile

from PIL import Image
import pytest

from dataset_atlas.adapters.places365 import Places365Adapter
from dataset_atlas.models import Dataset
from dataset_atlas.storage.indexed_tar import build_tar_index


def fixture(tmp_path,mode='valid',indexed=False):
    images=tmp_path/'val.tar';annotations=tmp_path/'annotations.tar';payloads={};labels=[]
    with tarfile.open(images,'w') as archive:
        for ordinal in range(4):
            name=f'Places365_val_{ordinal+1:08}.jpg';output=io.BytesIO()
            Image.new('RGB',(9,7),(ordinal*30,40,60)).save(output,format='JPEG');payload=output.getvalue()
            member=tarfile.TarInfo('val_256/'+name);member.size=len(payload);archive.addfile(member,io.BytesIO(payload))
            labels.append('/'+name+' '+str(ordinal//2));payloads[name]=payload
    if mode=='duplicate':labels[-1]=labels[0]
    if mode=='missing':labels.pop()
    if mode=='unknown_class':labels[0]=labels[0].rsplit(' ',1)[0]+' 9'
    with tarfile.open(annotations,'w') as archive:
        for name,payload in {'categories_places365.txt':b'/f/fixture_one 0\n/f/fixture_two 1\n',
                'places365_val.txt':('\n'.join(labels)+'\n').encode()}.items():
            member=tarfile.TarInfo(name);member.size=len(payload);archive.addfile(member,io.BytesIO(payload))
    config={'path':str(images),'sha256':hashlib.sha256(images.read_bytes()).hexdigest(),
        'annotations_path':str(annotations),'annotations_sha256':hashlib.sha256(annotations.read_bytes()).hexdigest(),
        'native_class_count':2,'native_images_per_class':2}
    if indexed:
        index=tmp_path/'index';proof=build_tar_index(images,index,source_sha256=config['sha256'],
            remote={'url':'https://fixture.invalid/val.tar','bytes':images.stat().st_size,'etag':'"fixture"','allowed_hosts':['fixture.invalid']},
            max_uncompressed_bytes=1_000_000,max_index_bytes=1_000_000)
        config.update(original_access_index=str(index),original_archive_path=str(images),path=str(index/'members.sqlite'),sha256=proof['checksums']['members.sqlite'])
    dataset=Dataset(id='fixture-places',name='Synthetic Places',release='fixture',snapshot_id='synthetic',adapter='places365',adapter_config=config)
    return Places365Adapter(dataset),payloads


@pytest.mark.parametrize('indexed',[False,True])
def test_complete_native_labels_and_original_members_join_exactly(tmp_path,indexed):
    adapter,payloads=fixture(tmp_path,indexed=indexed);source=adapter.prepare(adapter.plan(10,1_000_000))
    records=list(adapter.iter_sequential(source));assert len(records)==4 and len({record.id for record in records})==4
    assert [record.source['class_index'] for record in records]==[0,0,1,1]
    assert all(record.source['native_annotation_line'].startswith('/Places365_val_') and record.source['split']=='validation' for record in records)
    for record in records:
        asset=record.assets[0];handle=adapter.resolve_asset(source,asset.uri)
        assert handle.data==payloads[record.source['source_id']]
        if indexed:assert asset.sha256==handle.sha256
    page=adapter.iter_records(source,'2',2)
    assert [record.id for record in page.records]==[record.id for record in records[2:]] and page.next_cursor is None


@pytest.mark.parametrize('mode',['duplicate','missing','unknown_class'])
def test_native_annotation_defects_cannot_form_complete_coverage(tmp_path,mode):
    adapter,_=fixture(tmp_path,mode)
    with pytest.raises(ValueError):adapter.prepare(adapter.plan(10,1_000_000))


def test_raw_native_archive_rejects_duplicate_image_members(tmp_path):
    adapter,payloads=fixture(tmp_path)
    path=adapter._path();name=next(iter(payloads));payload=payloads[name]
    with tarfile.open(path,'a') as archive:
        member=tarfile.TarInfo('val_256/'+name);member.size=len(payload);archive.addfile(member,io.BytesIO(payload))
    adapter.config['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='Duplicate Places365 original image member'):
        adapter.prepare(adapter.plan(10,1_000_000))
