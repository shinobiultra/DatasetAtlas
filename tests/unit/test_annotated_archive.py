import json
import zipfile
import pytest
from dataset_atlas.adapters.annotated_archive import AnnotatedArchiveAdapter
from dataset_atlas.models import Dataset


def make(tmp_path, members, **config):
    path=tmp_path/'source.zip'
    with zipfile.ZipFile(path,'w') as archive:
        for name,value in members.items():archive.writestr(name,value)
    return AnnotatedArchiveAdapter(Dataset(id='tasks',name='Tasks',release='r',snapshot_id='s',adapter='annotated_archive',
        adapter_config={'path':str(path),'annotation_patterns':['*.json'],**config}))


def test_complete_tasks_and_stable_paging(tmp_path):
    task={'train':[{'input':[[1,2]],'output':[[2,1]]}],'test':[{'input':[[3,4]]}]}
    adapter=make(tmp_path,{'corpus/a.json':json.dumps(task),'corpus/b.json':json.dumps(task)},json_mode='document')
    source=adapter.prepare(adapter.plan(1,10000))
    first=adapter.iter_records(source);second=adapter.iter_records(source,first.next_cursor)
    assert adapter.count==2 and second.next_cursor is None
    assert first.records[0].source['train']==task['train']
    assert first.records[0].id!=second.records[0].id
    assert second.records[0].id==adapter.iter_records(source,'1').records[0].id


def test_csv_media_join_and_source_fields(tmp_path):
    adapter=make(tmp_path,{'release/metadata.csv':'id,img_filename,y,place,split\n1,bird.jpg,0,1,2\n','release/bird.jpg':b'original'},
        annotation_patterns=['release/metadata.csv'],mapping={'media':'img_filename'},media_prefix='release/')
    source=adapter.prepare(adapter.plan(100,10000));record=adapter.iter_records(source).records[0]
    assert record.source['place']=='1' and record.source['split']=='2'
    assert record.source['img_filename']=='bird.jpg'
    assert adapter.resolve_asset(source,record.assets[0].uri).data==b'original'


def test_archive_rejects_unsafe_members_and_budget(tmp_path):
    adapter=make(tmp_path,{'../bad.json':'{}'},json_mode='document')
    with pytest.raises(ValueError):adapter.count
    adapter=make(tmp_path,{'good.json':'{"long":"value"}'},json_mode='document',max_annotation_bytes=2)
    with pytest.raises(ValueError,match='byte limit'):adapter.count
    adapter=make(tmp_path,{'good.json':'{"_atlas_origin":{}}'},json_mode='document')
    with pytest.raises(ValueError,match='reserved'):adapter.count


def test_missing_media_is_an_error_not_silent_coverage(tmp_path):
    adapter=make(tmp_path,{'records.json':'[{"image":"absent.png"}]'},mapping={'media':'image'})
    source=adapter.prepare(adapter.plan(100,10000))
    with pytest.raises(ValueError,match='missing media'):adapter.iter_records(source)
