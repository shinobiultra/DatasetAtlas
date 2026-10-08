"""Synthetic native-member pagination; no generated coverage is published."""
import json
import sqlite3

from dataset_atlas.adapters.imagenet_c import ImageNetCAdapter
from dataset_atlas.models import Dataset


def test_later_native_pages_charge_only_selected_records_across_archives(tmp_path,monkeypatch):
    indices=[]
    for archive,corruptions in [('blur',['blur','blur']),('digital',['pixelate','jpeg','jpeg'])]:
        path=tmp_path/archive;path.mkdir();indices.append(str(path))
        (path/'receipt.json').write_text(json.dumps({'source_sha256':'a'*64}))
        with sqlite3.connect(path/'members.sqlite') as db:
            db.execute('CREATE TABLE members (name TEXT PRIMARY KEY,offset INTEGER,bytes INTEGER,sha256 TEXT)')
            for i,corruption in enumerate(corruptions):
                db.execute('INSERT INTO members VALUES (?,?,?,?)',(f'{corruption}/1/n00000001/{i}.JPEG',i*512,70,'b'*64))
    dataset=Dataset(id='fixture',name='Synthetic corruption metadata',release='r1',snapshot_id='s1',adapter='imagenet_c',
                    adapter_config={'indices':indices,'mapping':{'id':'source_id','media':'media_ref'}})
    adapter=ImageNetCAdapter(dataset)
    monkeypatch.setattr(adapter,'iter_sequential',lambda source:(_ for _ in ()).throw(AssertionError('Paging must not replay earlier records')))
    source=adapter.prepare(adapter.plan(2,5000))
    page=adapter.iter_records(source,cursor='1',limit=2)
    assert [r.source['archive'] for r in page.records]==['blur','digital']
    assert page.next_cursor=='3' and page.source_rows_read==2
    assert source.bytes_read==sum(len(r.model_dump_json().encode()) for r in page.records)
    source=adapter.prepare(adapter.plan(2,5000))
    last=adapter.iter_records(source,cursor='4',limit=2)
    assert len(last.records)==1 and last.next_cursor is None
    assert last.records[0].source['source_filename']=='2.JPEG'
    assert last.records[0].assets[0].sha256=='b'*64
