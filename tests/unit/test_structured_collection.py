import io,json,hashlib,zipfile
from pathlib import Path
from PIL import Image
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.structured_collection import StructuredCollectionAdapter


def fixture(tmp_path,monkeypatch,missing=False):
    output=io.BytesIO();Image.new('RGB',(8,6),'red').save(output,format='PNG');image=output.getvalue()
    path=tmp_path/'media.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr('train/image.png',image)
    annotation=tmp_path/'data.json';annotation.write_text(json.dumps({'data':[{'id':1,'question':'Which colour?','image':'absent.png' if missing else 'image.png','answers':['red']},{'id':2,'question':'Same image?','image':'image.png'}]}))
    dataset=Dataset(id='questions',name='Questions',release='r',snapshot_id='s',adapter='structured_collection',adapter_config={
        'train_path':str(annotation),'annotations':[{'path_key':'train_path','records_key':'data','split':'train','media_template':'train/{image}','media_archive':'images'}],
        'mapping':{'id':'id','question':'question'},'source_files':[{'path':str(annotation),'sha256':hashlib.sha256(annotation.read_bytes()).hexdigest()}],
        'remote_archives':{'images':{'etag':'"release"'}}})
    class Remote(io.BytesIO):bytes_fetched=50
    monkeypatch.setattr(StructuredCollectionAdapter,'_remote',lambda self,key,budget:Remote(path.read_bytes()))
    return StructuredCollectionAdapter(dataset),image,annotation


def test_complete_join_preserves_repeated_images_and_original_answers(tmp_path,monkeypatch):
    adapter,image,_=fixture(tmp_path,monkeypatch);source=adapter.prepare(adapter.plan(1,10000))
    validation=adapter.validate_media(10000);assert validation['referenced_images']==1
    first=adapter.iter_records(source);second=adapter.iter_records(source,first.next_cursor)
    assert first.records[0].id!=second.records[0].id
    assert first.records[0].asset_ids==second.records[0].asset_ids
    assert first.records[0].source['answers']==['red'] and 'answers' not in second.records[0].source
    assert adapter.resolve_asset(source,second.records[0].assets[0].uri).data==image
    assert adapter.count==2 and second.next_cursor is None


def test_missing_images_changed_annotations_and_output_bound(tmp_path,monkeypatch):
    adapter,_,annotation=fixture(tmp_path,monkeypatch,missing=True)
    with pytest.raises(ValueError,match='missing ZIP'):adapter.validate_media(10000)
    adapter,image,annotation=fixture(tmp_path,monkeypatch)
    source=adapter.prepare(adapter.plan(1,1))
    with pytest.raises(ValueError,match='byte budget'):adapter.resolve_asset(source,'zip/images/train/image.png')
    annotation.write_text('[]')
    with pytest.raises(ValueError,match='checksum'):adapter.prepare(adapter.plan(1,10000))


def test_fresh_adapter_preserves_nonordinal_source_ids(tmp_path,monkeypatch):
    adapter,_,_=fixture(tmp_path,monkeypatch)
    dataset=adapter.dataset.model_copy(deep=True)
    source=adapter.prepare(adapter.plan(2,10000));first=adapter.iter_records(source).records
    assert dataset.adapter_config['mapping']['id']=='id'
    assert adapter.dataset.adapter_config['mapping']['id']=='id'
    fresh=StructuredCollectionAdapter(adapter.dataset)
    again=fresh.iter_records(fresh.prepare(fresh.plan(2,10000))).records
    assert [r.id for r in first]==[r.id for r in again]
    assert first[0].source['_atlas_origin']['identity']=='train:1'


def test_split_csv_and_compound_ids_preserve_source_fields(tmp_path):
    path = tmp_path/'questions.csv'
    path.write_text('id,category,question,answer\n1,near,Where?,here\n1,far,Where?,there\n')
    dataset = Dataset(id='csv',name='CSV fixture',release='r',snapshot_id='s',adapter='structured_collection',adapter_config={
        'path':str(path),'annotations':[{'path_key':'path','format':'csv','split':'test'}],
        'mapping':{'id':'id','question':'question'},'identity_fields':['category','id']})
    adapter=StructuredCollectionAdapter(dataset)
    records=adapter.iter_records(adapter.prepare(adapter.plan(10,10000))).records
    assert len({r.id for r in records})==2
    assert records[0].source['id']=='1' and records[1].source['answer']=='there'
    assert records[0].question=='Where?'


def test_inventory_images_are_bounded_checked_and_share_asset_identity(tmp_path,monkeypatch):
    adapter,image,path=fixture(tmp_path,monkeypatch)
    rows=[{'id':1,'image':'a.png','condition_image':'a.png'}]
    path.write_text(json.dumps(rows))
    inventory=tmp_path/'inventory.json';inventory.write_text(json.dumps({'files':{'a.png':{'bytes':len(image),'git_blob_sha1':hashlib.sha1(f'blob {len(image)}\0'.encode()+image).hexdigest()}}}))
    adapter.config.update(annotations=[{'path_key':'train_path','split':'train','media_templates':['{image}','{condition_image}']}],
        source_files=[],media_inventory_path=str(inventory),media_inventory_sha256=hashlib.sha256(inventory.read_bytes()).hexdigest(),
        remote_cache_root=str(tmp_path/'cache'),media_base_url='https://example.org/pinned',media_allowed_hosts=['example.org'])
    local=tmp_path/'image.png';local.write_bytes(image)
    monkeypatch.setattr('dataset_atlas.adapters.structured_collection.HttpsFetcher.fetch',lambda *a,**k:local)
    assert adapter.validate_media(10000)['referenced_images']==1
    source=adapter.prepare(adapter.plan(10,10000));record=adapter.iter_records(source).records[0]
    assert len(record.assets)==2 and len(set(record.asset_ids))==1
    assert adapter.resolve_asset(source,record.assets[0].uri).data==image
    local.write_bytes(b'0'*len(image))
    with pytest.raises(ValueError,match='Git object'):adapter.resolve_asset(source,record.assets[0].uri)


def test_media_arrays_and_url_paths_use_only_recipe_archives(tmp_path,monkeypatch):
    adapter,image,path=fixture(tmp_path,monkeypatch)
    path.write_text(json.dumps([{'id':1,'images':['train/image.png','train/image.png'],'image_link':'http://untrusted.example/train/image.png'}]))
    adapter.config.update(source_files=[],annotations=[{'path_key':'train_path','split':'evaluation','media_paths_field':'images','media_archive':'images','media_path_url_field':'image_link','media_archive_by_prefix':{'train':'images'}}])
    record=adapter.iter_records(adapter.prepare(adapter.plan(10,10000))).records[0]
    assert len(record.assets)==3 and len(set(record.asset_ids))==1
    assert all(a.uri=='zip/images/train/image.png' for a in record.assets)
    assert adapter.validate_media(10000)['referenced_images']==1
    adapter.config['annotations'][0]['media_archive_by_prefix']={}
    del adapter._annotation_rows
    with pytest.raises(ValueError,match='no declared archive'):adapter._rows()


def test_ordered_text_segments_are_joined_without_changing_originals(tmp_path):
    from dataset_atlas.models import Dataset
    from dataset_atlas.adapters.structured_collection import StructuredCollectionAdapter
    import json
    path=tmp_path/'segments.json';path.write_text(json.dumps([{'base':['A',' word'], 'src':['Other',' word']}]))
    a=StructuredCollectionAdapter(Dataset(id='segments',name='Fixture',release='r',snapshot_id='s',adapter='structured_collection',adapter_config={
        'path':str(path),'annotations':[{'path_key':'path','split':'train'}],'text_parts_field':'base','mapping':{'text':'_atlas_text'}}))
    record=a.iter_records(a.prepare(a.plan(10,10000))).records[0]
    assert record.text=='A word' and record.source['base']==['A',' word'] and record.source['src']==['Other',' word']


def test_fixed_width_caption_rows_preserve_order_and_reject_bad_width(tmp_path):
    import json
    from dataset_atlas.models import Dataset
    from dataset_atlas.adapters.structured_collection import StructuredCollectionAdapter
    path=tmp_path/'captions.json';path.write_text(json.dumps([[123,'True caption','False caption']]))
    config={'path':str(path),'annotations':[{'path_key':'path','split':'one','array_columns':['image_id','yes','no'],
        'choices_columns':['yes','no'],'correct_choice_index':0,'text_from_first_choice':True,
        'media_stem_field':'image_id','media_stem_width':12,'media_template':'val/{_stem}.jpg','media_archive':'coco'}],
        'mapping':{'text':'_atlas_text','choices':'_atlas_choices'},'remote_archives':{'coco':{'etag':'"test"'}}}
    a=StructuredCollectionAdapter(Dataset(id='captions',name='Fixture',release='r',snapshot_id='s',adapter_config=config))
    record=a.iter_records(a.prepare(a.plan(10,10000))).records[0]
    assert record.text=='True caption' and record.choices==['True caption','False caption']
    assert record.source['_atlas_correct_choice_index']==0 and record.source['image_id']==123
    assert record.assets[0].uri=='zip/coco/val/000000000123.jpg'
    path.write_text('[[123,"only one option"]]')
    with pytest.raises(ValueError,match='width'):StructuredCollectionAdapter(a.dataset)._rows()


def test_native_conditions_keep_distinct_targets_and_explicit_absence(tmp_path):
    rows=[{'image_name':'a','label':'2'},{'image_name':'b','label':'No illusion'}]
    path=tmp_path/'rows.json';path.write_text(json.dumps(rows))
    files={name:{'bytes':10,'sha256':'a'*64} for name in ['repo/illusion/a.jpg','repo/raw/a.jpg','repo/illusion/b.jpg','repo/control/a.jpg','repo/control/b.jpg']}
    inventory=tmp_path/'images.json';inventory.write_text(json.dumps({'files':files}))
    variants=[{'template':'{_prefix}/illusion/{image_name}.jpg','condition':'illusion','target_field':'label'},
        {'template':'{_prefix}/raw/{image_name}.jpg','condition':'raw','target_field':'label','absent_when':{'field':'label','values':['No illusion']}},
        {'template':'{_prefix}/control/{image_name}.jpg','condition':'control','target':'No illusion'}]
    dataset=Dataset(id='variants',name='Fixture',release='r',snapshot_id='s',adapter='structured_collection',adapter_config={
        'path':str(path),'annotations':[{'path_key':'path','split':'test','media_prefix':'repo','media_variants':variants}],
        'mapping':{'id':'image_name'},'media_inventory_path':str(inventory),'media_inventory_sha256':hashlib.sha256(inventory.read_bytes()).hexdigest()})
    adapter=StructuredCollectionAdapter(dataset);assert adapter.validate_media(10000)['referenced_images']==5
    records=adapter.iter_records(adapter.prepare(adapter.plan(10,10000))).records
    assert [a.metadata['target'] for a in records[0].assets]==['2','2','No illusion']
    assert len(records[1].assets)==2 and records[1].source['_atlas_absent_conditions']==['raw']
    assert records[0].source['label']=='2'
    # Undeclared absence remains an error rather than silently dropping a condition.
    del files['repo/control/b.jpg'];inventory.write_text(json.dumps({'files':files}))
    dataset.adapter_config['media_inventory_sha256']=hashlib.sha256(inventory.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='missing inventory'):StructuredCollectionAdapter(dataset).validate_media(10000)


def test_malformed_upstream_document_can_be_inspected_as_explicit_raw_text(tmp_path):
    path=tmp_path/'broken.jsonl';path.write_text('<html>Upstream error committed as a source file</html>')
    dataset=Dataset(id='raw',name='Fixture',release='r',snapshot_id='s',adapter='structured_collection',adapter_config={
        'path':str(path),'annotations':[{'path_key':'path','format':'text','split':'malformed','source_status':'Invalid native JSONL'}],'mapping':{'text':'text'}})
    adapter=StructuredCollectionAdapter(dataset);record=adapter.iter_records(adapter.prepare(adapter.plan(1,10000))).records[0]
    assert record.text==path.read_text()
    assert record.source['_atlas_source_status']=='Invalid native JSONL'
    assert not record.assets


def test_native_annotation_join_preserves_fields_and_rejects_defects(tmp_path,monkeypatch):
    adapter,_,path=fixture(tmp_path,monkeypatch)
    path.write_text('[{"id":1,"image_id":7,"question":"Where?"}]')
    joined=tmp_path/'images.json';joined.write_text('[{"image_id":7,"url":"http://source.example/train/image.png","width":8}]')
    adapter.config.update(source_files=[],images_path=str(joined),annotations=[{'path_key':'train_path','split':'test',
        'joins':[{'path_key':'images_path','on':'image_id','key':'image_id','field':'image_metadata'}],
        'media_path_url_field':'image_metadata.url','media_archive_by_prefix':{'train':'images'}}])
    record=adapter.iter_records(adapter.prepare(adapter.plan(10,10000))).records[0]
    assert record.source['image_metadata']['width']==8 and record.question=='Where?'
    assert record.assets[0].uri=='zip/images/train/image.png'
    for value,match in [('[{"image_id":7},{"image_id":7}]','Duplicate'),('[{"image_id":8}]','no matching'),
                        ('[{"image_id":7,"url":"http://x/train/image.png"},{"image_id":8}]','Unmatched')]:
        joined.write_text(value);adapter.__dict__.pop('_annotation_rows',None)
        with pytest.raises(ValueError,match=match):adapter._rows()


def test_native_text_lists_preserve_line_numbers_and_overlapping_memberships(tmp_path):
    path = tmp_path/'prompts.txt';path.write_text('First prompt\n\n Second prompt \n')
    dataset = Dataset(id='prompts', name='Fixture', release='r', snapshot_id='s', adapter='structured_collection', adapter_config={
        'path': str(path), 'annotations': [{'path_key': 'path', 'format': 'text_lines', 'split': split} for split in ['all', 'train']],
        'mapping': {'id': 'line', 'text': 'text'}})
    adapter = StructuredCollectionAdapter(dataset)
    records = adapter.iter_records(adapter.prepare(adapter.plan(10, 10000))).records
    assert len(records) == 4 and len({r.id for r in records}) == 4
    assert records[1].source['line'] == 3 and records[1].text == ' Second prompt '
    assert records[0].text == records[2].text
