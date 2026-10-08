import csv
import json
import zipfile

import pytest

from dataset_atlas.converters.collections import flickr30k_mirror,miap_images,shapeworld_examples,sorrybench_variants,pile_heldout,objaverse_annotations


def shape_archive(path,bad=False):
    base='ShapeWorld-fixture/examples/agreement/existential-full'
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr(base+'/world_model.json',json.dumps([{'entities':[]},{'entities':[]}]))
        archive.writestr(base+'/caption_model.json',json.dumps([[{'a':1},{'a':2}],[{'a':3}]]))
        archive.writestr(base+'/alternatives.txt','2\n1\n')
        archive.writestr(base+'/caption.txt','first caption\nsecond caption\n\nthird caption\n\n')
        archive.writestr(base+'/agreement.txt','1.0;0.0\n1.0\n' if not bad else '1.0\n1.0\n')
        for i in range(2):archive.writestr(f'{base}/world-{i}.png',b'fixture-only')


def test_shape_keeps_alternatives_and_native_model_rows(tmp_path):
    path=tmp_path/'source.zip';shape_archive(path)
    result=shapeworld_examples({}, {'media_archive':path},tmp_path/'out',lambda:None)
    rows=[json.loads(line) for line in result['path'].read_text().splitlines()]
    assert result['count']==2
    assert rows[0]['captions']==['first caption','second caption']
    assert rows[0]['agreements']==[1.0,0.0]
    assert rows[0]['caption_model']==[{'a':1},{'a':2}]
    assert rows[1]['caption']=='third caption'


def test_shape_rejects_changed_caption_to_label_alignment(tmp_path):
    path=tmp_path/'source.zip';shape_archive(path,bad=True)
    with pytest.raises(ValueError,match='alternatives disagree'):
        shapeworld_examples({}, {'media_archive':path},tmp_path/'out',lambda:None)


def test_flickr_decodes_lists_without_executing_native_fields(tmp_path):
    path=tmp_path/'source.csv'
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=['raw','sentids','filename','img_id','split']);writer.writeheader()
        writer.writerow({'raw':"['one', 'two']",'sentids':'[8, 9]','filename':'a.jpg','img_id':'1','split':'train'})
    result=flickr30k_mirror({}, {'annotation_csv':path},tmp_path/'out',lambda:None)
    row=json.loads(result['path'].read_text())
    assert row['raw']=="['one', 'two']" and row['captions']==['one','two'] and row['sentence_ids']==[8,9]
    path.write_text('raw,sentids,filename,img_id,split\n__import__("os").getcwd(),[],a.jpg,1,train\n')
    with pytest.raises((ValueError,SyntaxError)):flickr30k_mirror({}, {'annotation_csv':path},tmp_path/'bad',lambda:None)


def test_miap_preserves_native_box_order_and_checks_key_join(tmp_path):
    inputs={}
    for i,split in enumerate(('train','val','test')):
        box=tmp_path/(split+'.csv');keys=tmp_path/(split+'.lst');inputs['boxes_'+split]=box;inputs['images_'+split]=keys
        image_id=f'{i:016x}'
        box.write_text('ImageID,GenderPresentation,AgePresentation,XMin\n'+image_id+',Unknown,Adult,0.10\n'+image_id+',Feminine,Unknown,0.05\n')
        keys.write_text(('validation' if split=='val' else split)+'/'+image_id+'\n')
    result=miap_images({},inputs,tmp_path/'out',lambda:None)
    rows=[json.loads(line) for line in result['path'].read_text().splitlines()]
    assert result['count']==3
    assert rows[0]['box_count']==2 and rows[0]['boxes'][0]['XMin']=='0.10'
    assert rows[0]['boxes'][1]['source_box_row']==1
    inputs['images_train'].write_text('train/missing\n')
    with pytest.raises(ValueError,match='no native box'):miap_images({},inputs,tmp_path/'bad',lambda:None)


def test_sorry_native_unicode_and_missing_turns_remain_intact(tmp_path):
    inputs={}
    for name,turn in [('question.jsonl','first\u0085second\u2028third'),('question_variant.jsonl',None)]:
        path=tmp_path/name;inputs[name]=path
        path.write_text(json.dumps({'question_id':1,'category':'fixture','prompt_style':'fixture','turns':[turn]},ensure_ascii=False)+'\n')
    result=sorrybench_variants({'source_order':list(inputs)},inputs,tmp_path/'out',lambda:None)
    with result['path'].open() as stream:rows=[json.loads(line) for line in stream]
    assert rows[0]['text']=='first\u0085second\u2028third'
    assert rows[1]['text'] is None and rows[1]['turns']==[None] and rows[1]['native_null_turns']==1
    inputs['question_variant.jsonl'].write_text(json.dumps({'question_id':2,'category':'fixture','prompt_style':'fixture','turns':['changed']})+'\n')
    with pytest.raises(ValueError,match='membership changed'):
        sorrybench_variants({'source_order':list(inputs)},inputs,tmp_path/'bad',lambda:None)


def test_pile_heldout_preserves_native_text_and_heterogeneous_metadata(tmp_path):
    import pyarrow.parquet as pq
    inputs={};native=[]
    for split,meta in [('validation',{'pile_set_name':'fixture-a','nested':{'native':[1,None]}}),
                       ('test',{'pile_set_name':'fixture-b','url':'https://example.org/fixture'})]:
        value={'text':'first\u0085second\u2028third\r\nfourth','meta':meta};native.append(value)
        inputs[split]=tmp_path/(split+'.jsonl');inputs[split].write_text(json.dumps(value,ensure_ascii=False)+'\n')
    result=pile_heldout({},inputs,tmp_path/'out',lambda:None);rows=pq.read_table(result['path']).to_pylist()
    assert len(rows)==2 and [r['source_split'] for r in rows]==['validation','test']
    for row,value in zip(rows,native,strict=True):
        assert row['text']==value['text'] and json.loads(row['native_meta_json'])==value['meta']
    inputs['test'].write_text(json.dumps({'text':'fixture','meta':{},'unexpected':'field'})+'\n')
    with pytest.raises(ValueError,match='schema changed'):pile_heldout({},inputs,tmp_path/'bad',lambda:None)


def test_objaverse_native_uid_and_licence_forms_are_preserved_with_exact_joins(tmp_path):
    import gzip
    import hashlib
    import pyarrow.parquet as pq
    def source(name, value):
        path=tmp_path/name
        with gzip.open(path,'wt') as stream:json.dump(value,stream)
        return path
    uids=['a'*32,'NonHexNativeUID16']
    metadata={uid:{'uid':uid,'name':'fixture','description':'fixture metadata',
                   'license':'by' if i==0 else {'slug':'by-sa','native_extra':None},
                   'faceCount':i+1,'vertexCount':3,'original_nested':{'values':[None,i]}}
              for i,uid in enumerate(uids)}
    paths={uid:'glbs/000-000/'+uid+'.glb' for uid in uids}
    inputs={'object_paths':source('paths.json.gz',paths),
            'lvis_annotations':source('lvis.json.gz',{'second':[uids[0]],'first':uids}),
            'metadata':source('metadata.json.gz',metadata)}
    params={'metadata_order':['metadata']}
    result=objaverse_annotations(params,inputs,tmp_path/'out',lambda:None)
    rows=pq.read_table(result['path']).to_pylist()
    assert [r['source_id'] for r in rows]==uids
    assert rows[0]['native_lvis_categories']==['second','first']
    assert [r['license_slug'] for r in rows]==['by','by-sa']
    for row,uid in zip(rows,uids,strict=True):
        assert json.loads(row['native_annotation_json'])==metadata[uid]
        assert row['source_metadata_sha256']==hashlib.sha256(inputs['metadata'].read_bytes()).hexdigest()
    inputs['object_paths']=source('bad-paths.json.gz',paths | {uids[0]:'../outside.glb'})
    with pytest.raises(ValueError,match='Unsafe or mismatched'):
        objaverse_annotations(params,inputs,tmp_path/'bad',lambda:None)
    inputs['object_paths']=source('paths.json.gz',paths)
    inputs['metadata']=source('incomplete.json.gz',{uids[0]:metadata[uids[0]]})
    with pytest.raises(ValueError,match='complete object population'):
        objaverse_annotations(params,inputs,tmp_path/'missing',lambda:None)


def test_objaverse_entity_identity_matches_complete_snapshot(tmp_path):
    import hashlib
    import pyarrow as pa
    import pyarrow.parquet as pq
    from dataset_atlas.adapters.objaverse import ObjaverseAdapter
    from dataset_atlas.models import Dataset,stable_id
    from dataset_atlas.queries.parquet import build_parquet_snapshot
    path=tmp_path/'native.parquet'
    uid='a'*32
    pq.write_table(pa.Table.from_pylist([{'source_id':uid,'media_ref':'glbs/000-000/'+uid+'.glb'}]),path)
    dataset=Dataset(id='objaverse',name='Synthetic object identity',release='pinned',snapshot_id='native',adapter='objaverse',
        coverage={'unit':'entity'},adapter_config={'path':str(path),'format':'parquet','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'mapping':{'id':'source_id','media':'media_ref','media_modality':'model3d'}})
    adapter=ObjaverseAdapter(dataset);source=adapter.prepare(adapter.plan(1,10000))
    records=list(adapter.iter_sequential(source))
    assert records[0].unit=='entity' and records[0].id==stable_id('objaverse','pinned','entity',uid)
    assert records[0].source['source_id']==uid and records[0].assets[0].modality=='model3d'
    build_parquet_snapshot(records,[],tmp_path/'snapshot',root=tmp_path,dataset_id='objaverse',release_id='pinned',
        snapshot_id='native',unit='entity',expected_count=1,population_scope='complete')
