"""Synthetic native taxonomy joins and immutable original references."""
import hashlib
import json
import sqlite3

import pytest

from dataset_atlas.adapters.inaturalist import INaturalistAdapter
from dataset_atlas.models import Dataset


def fixture(tmp_path,monkeypatch):
    indices=[]
    for name in ('val.json.tar','val.tar'):
        index=tmp_path/name;index.mkdir();indices.append(str(index))
        with sqlite3.connect(index/'members.sqlite') as db:
            db.execute('CREATE TABLE members (name TEXT PRIMARY KEY,bytes INTEGER,sha256 TEXT)')
            if name=='val.tar':
                db.executemany('INSERT INTO members VALUES (?,?,?)',[(f'val/class/{i}.jpg',20,str(i)*64) for i in (1,2)])
        digest=hashlib.sha256((index/'members.sqlite').read_bytes()).hexdigest()
        (index/'receipt.json').write_text(json.dumps({'checksums':{'members.sqlite':digest}}))
    document={'info':{'version':'2021'},'images':[{'id':i,'file_name':f'val/class/{i}.jpg','license':7,'latitude':i} for i in (1,2)],
        'annotations':[{'id':i+10,'image_id':i,'category_id':99} for i in (1,2)],
        'categories':[{'id':99,'name':'native taxon','kingdom':'native kingdom'}],'licenses':[{'id':7,'name':'native licence','url':'https://example.invalid/licence'}]}
    def read(*a):return json.dumps(document).encode(),{'sha256':'a'*64}
    monkeypatch.setattr(INaturalistAdapter,'_read',read)
    dataset=Dataset(id='fixture',name='Synthetic native taxonomy',release='2021',snapshot_id='s1',adapter='inaturalist',
        adapter_config={'indices':indices,'annotation_archive_name':'val.json.tar','annotation_member':'val.json','image_archive_name':'val.tar',
            'mapping':{'id':'source_id','media':'media_ref'}})
    return dataset,document


def test_native_taxonomy_licenses_and_later_pages_are_exact(tmp_path,monkeypatch):
    dataset,native=fixture(tmp_path,monkeypatch);adapter=INaturalistAdapter(dataset)
    source=adapter.prepare(adapter.plan(1,10000));record=adapter.iter_records(source,cursor='1').records[0]
    assert record.source['image']==native['images'][1]
    assert record.source['category']==native['categories'][0] and record.source['license']==native['licenses'][0]
    assert record.source['annotation']==native['annotations'][1]
    assert record.assets[0].uri=='val.tar/val/class/2.jpg' and record.assets[0].sha256=='2'*64
    assert source.bytes_read==len(record.model_dump_json().encode())
    assert adapter.validate_media(100000,lambda:None)['all_archive_image_members_joined']


@pytest.mark.parametrize('defect',['duplicate','orphan','missing_image','missing_license','unsafe_path','unmatched_image'])
def test_native_join_defects_fail_before_activation(tmp_path,monkeypatch,defect):
    dataset,native=fixture(tmp_path,monkeypatch)
    if defect=='duplicate':native['annotations'][1]['image_id']=1
    elif defect=='orphan':native['annotations'][0]['category_id']=100
    elif defect=='missing_image':native['annotations'].pop()
    elif defect=='missing_license':native['images'][0]['license']=8
    elif defect=='unsafe_path':native['images'][0]['file_name']='../outside.jpg'
    else:native['images'].pop();native['annotations'].pop()
    with pytest.raises(ValueError):INaturalistAdapter(dataset).validate_media(100000,lambda:None)
