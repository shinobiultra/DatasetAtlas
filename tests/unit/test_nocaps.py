import hashlib,json
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.nocaps import NocapsAdapter


def fixture(tmp_path):
    path=tmp_path/'annotations.json'
    captions=[{'id':i,'image_id':11,'caption':f'caption {i}'} for i in range(10)]
    path.write_text(json.dumps({'images':[{'id':11,'file_name':'a.jpg'}],'annotations':captions}))
    test=tmp_path/'test.json';test.write_text(json.dumps({'images':[{'id':21,'file_name':'b.jpg'}]}))
    inventory=tmp_path/'inventory.json';inventory.write_text(json.dumps({'files':{n:{'bytes':50,'etag':'"v1"'} for n in ['validation/a.jpg','test/b.jpg']}}))
    config={'val_path':str(path),'test_path':str(test),'mapping':{'id':'id','text':'_atlas_caption_text'},
        'annotations':[{'path_key':'val_path','split':'validation','records_key':'images','media_template':'validation/{file_name}',
            'joins':[{'path_key':'val_path','records_key':'annotations','key':'image_id','on':'id','field':'native_captions','many':True}]},
            {'path_key':'test_path','split':'test','records_key':'images','media_template':'test/{file_name}'}],
        'media_inventory_path':str(inventory),'media_inventory_sha256':hashlib.sha256(inventory.read_bytes()).hexdigest()}
    return Dataset(id='nocaps',name='Fixture',release='r',snapshot_id='s',adapter='nocaps',adapter_config=config),path,captions


def test_native_caption_groups_and_test_without_labels(tmp_path):
    dataset,path,captions=fixture(tmp_path);adapter=NocapsAdapter(dataset);records=adapter.iter_records(adapter.prepare(adapter.plan(10,100000))).records
    assert len(records)==2 and records[0].source['native_captions']==captions
    assert records[0].text=='\n'.join(c['caption'] for c in captions)
    assert records[1].text is None and 'native_captions' not in records[1].source
    assert records[1].assets[0].uri=='file/test/b.jpg'


def test_incomplete_duplicate_and_unmatched_native_captions_fail(tmp_path):
    dataset,path,captions=fixture(tmp_path);original=json.loads(path.read_text())
    for rows,pattern in [(captions[:9],'ten native'),(captions[:-1]+[captions[0]],'Duplicate'),
                          (captions+[{'id':99,'image_id':999,'caption':'unmatched'}],'Unmatched')]:
        path.write_text(json.dumps({**original,'annotations':rows}))
        with pytest.raises(ValueError,match=pattern):NocapsAdapter(dataset).prepare(NocapsAdapter(dataset).plan(10,100000))
