import io,zipfile
from PIL import Image
import numpy as np
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.classic_vision import ClassicVisionAdapter


def test_flowers_native_splits_and_original_pixels(tmp_path):
    from scipy.io import savemat
    source=tmp_path/'flowers.zip';image=io.BytesIO();Image.new('RGB',(8,8),'blue').save(image,'JPEG')
    with zipfile.ZipFile(source,'w') as z:
        for i in range(1,4):z.writestr(f'jpg/image_{i:05d}.jpg',image.getvalue())
    labels=tmp_path/'labels.mat';splits=tmp_path/'splits.mat'
    savemat(labels,{'labels':np.array([[2,1,2]])});savemat(splits,{'trnid':[[1]],'valid':[[3]],'tstid':[[2]]})
    dataset=Dataset(id='flowers',name='Fixture',release='r',snapshot_id='s',adapter='classic_vision',adapter_config={
        'path':str(source),'labels_path':str(labels),'splits_path':str(splits),'dataset_kind':'flowers102'})
    adapter=ClassicVisionAdapter(dataset);prepared=adapter.prepare(adapter.plan(10,10000));records=adapter.iter_records(prepared).records
    assert [(r.source['class_id'],r.source['split']) for r in records]==[(2,'train'),(1,'test'),(2,'val')]
    assert adapter.resolve_asset(prepared,records[-1].assets[0].uri).data==image.getvalue()
    savemat(splits,{'trnid':[[1]],'valid':[[1]],'tstid':[[2]]})
    with pytest.raises(ValueError,match='overlap'):ClassicVisionAdapter(dataset)._rows()


def test_aircraft_labels_and_geometry_join(tmp_path):
    source=tmp_path/'aircraft.zip';prefix='fgvc-aircraft-2013b/data/'
    with zipfile.ZipFile(source,'w') as z:
        z.writestr(prefix+'images_box.txt','1 1 2 30 40\n2 3 4 50 60\n3 5 6 70 80\n')
        z.writestr(prefix+'images_size.txt','1 100 200\n2 100 200\n3 100 200\n')
        for i,split in enumerate(['train','val','test'],1):
            z.writestr(prefix+f'images_{split}.txt',str(i)+'\n');z.writestr(prefix+f'images/{i}.jpg',b'image')
            for field in ['variant','family','manufacturer']:z.writestr(prefix+f'images_{field}_{split}.txt',f'{i} Multi word {field}\n')
    dataset=Dataset(id='aircraft',name='Fixture',release='r',snapshot_id='s',adapter='classic_vision',adapter_config={'path':str(source),'dataset_kind':'aircraft'})
    adapter=ClassicVisionAdapter(dataset);records=adapter.iter_records(adapter.prepare(adapter.plan(10,10000))).records
    assert len(records)==3 and records[-1].source['manufacturer']=='Multi word manufacturer'
    assert records[-1].source['bounding_box_xyxy_1based']==[5,6,70,80]


def test_cub_boxes_parts_attributes_and_source_ids(tmp_path):
    source=tmp_path/'cub.zip';prefix='CUB_200_2011/'
    tables={'images.txt':'1 001.Bird/a.jpg\n','classes.txt':'1 Bird\n','image_class_labels.txt':'1 1\n','train_test_split.txt':'1 0\n',
            'bounding_boxes.txt':'1 2.0 3.0 4.0 5.0\n','parts/parts.txt':'1 beak\n','parts/part_locs.txt':'1 1 4.5 5.5 1\n',
            'attributes/image_attribute_labels.txt':'1 1 1 4 2.5\n'}
    with zipfile.ZipFile(source,'w') as z:
        for name,text in tables.items():z.writestr(prefix+name,text)
        z.writestr('attributes.txt','1 has_wing_color::blue\n');z.writestr(prefix+'images/001.Bird/a.jpg',b'image')
    adapter=ClassicVisionAdapter(Dataset(id='cub',name='Fixture',release='r',snapshot_id='s',adapter='classic_vision',adapter_config={
        'path':str(source),'dataset_kind':'cub_200_2011','parts_per_image':1,'attributes_per_image':1}))
    record=adapter.iter_records(adapter.prepare(adapter.plan(1,10000))).records[0]
    assert record.source['class_name']=='Bird' and record.source['split']=='test'
    assert record.source['parts']==[{'part_id':1,'name':'beak','x':4.5,'y':5.5,'visible':True}]
    assert record.source['attributes'][0]['name']=='has_wing_color::blue'
    assert record.source['attributes'][0]['annotation_time']==2.5


def test_food_native_taxonomy_splits_and_images(tmp_path):
    import zipfile
    from dataset_atlas.models import Dataset
    from dataset_atlas.adapters.classic_vision import ClassicVisionAdapter
    path=tmp_path/'food.zip'
    with zipfile.ZipFile(path,'w') as z:
        for name,text in {'classes.txt':'apple_pie\npizza\n','labels.txt':'Apple pie\nPizza\n','train.txt':'apple_pie/a\n','test.txt':'pizza/b\n'}.items():z.writestr('food-101/meta/'+name,text)
        z.writestr('food-101/images/apple_pie/a.jpg',b'fixture');z.writestr('food-101/images/pizza/b.jpg',b'fixture')
    adapter=ClassicVisionAdapter(Dataset(id='food',name='Food',release='r',snapshot_id='s',adapter='classic_vision',adapter_config={'path':str(path),'dataset_kind':'food101'}))
    rows=adapter._rows()
    assert [r['display_label'] for r in rows]==['Apple pie','Pizza']
    assert [r['split'] for r in rows]==['train','test']
    assert adapter.count==2


def test_caltech_nested_release_annotations_and_background(tmp_path):
    import tarfile
    from scipy.io import savemat
    from dataset_atlas.preparation import PreparationManager
    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry
    import yaml,json
    def mat(values):
        result=io.BytesIO();savemat(result,values);return result.getvalue()
    image=io.BytesIO();Image.new('RGB',(5,4)).save(image,'JPEG')
    images={'101_ObjectCategories/Faces/image_0001.jpg':image.getvalue(),
            '101_ObjectCategories/BACKGROUND_Google/image_0001.jpg':image.getvalue()}
    annotations={'Annotations/Faces_2/annotation_0001.mat':mat({'box_coord':[[1,4,1,5]],'obj_contour':[[0,1],[0,1]]}),
        'Annotations/FeatureDetectionQuality.mat':mat({'Features':{'name':'Faces_2','Good_Pts':[[2]],'Total_Pts':[[3]]}}),
        'Annotations/progress.mat':mat({'Status':1})}
    outer=tmp_path/'original.zip'
    with zipfile.ZipFile(outer,'w') as z:
        for name,entries in [('images.tgz',images),('annotations.tar',annotations)]:
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
                for member,data in entries.items():
                    info=tarfile.TarInfo(member);info.size=len(data);archive.addfile(info,io.BytesIO(data))
            z.writestr(name,buffer.getvalue())
    dataset=Dataset(id='caltech-test',name='Fixture',release='r',adapter='classic_vision',coverage={'total_count':2},adapter_config={
        'dataset_kind':'caltech101','path':str(outer),'outer_path':str(outer),'repack_members':[
            {'source_key':'outer_path','member':'images.tgz','target_key':'path'},
            {'source_key':'outer_path','member':'annotations.tar','target_key':'annotations_path'}]})
    directory=tmp_path/'registry/datasets';directory.mkdir(parents=True)
    (directory/'caltech.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    manager=PreparationManager(tmp_path);plan=manager.plan(dataset.id,1_000_000,1_000_000);run(tmp_path,plan['id'])
    registry=Registry(tmp_path);prepared=registry.dataset(dataset.id);adapter=ClassicVisionAdapter(prepared)
    rows=adapter._rows()
    assert rows[0]['annotation_status']=='not_released_for_background'
    assert rows[1]['native_annotation']['box_coord']==[[1,4,1,5]]
    assert rows[1]['native_feature_quality']['Good_Pts']==2
    assert rows[1]['native_feature_quality']['source_category']=='Faces_2'
    receipt=json.loads((registry.active_directory(dataset.id)/'receipt.json').read_text())
    assert len(receipt['derived_sources'])==2
    assert {s['source_member'] for s in receipt['derived_sources']}=={'images.tgz','annotations.tar'}
    # Unknown orphan annotations are an error, not silently ignored.
    prepared.adapter_config.pop('derived_archive_checksums')
    with zipfile.ZipFile(prepared.adapter_config['annotations_path'],'a') as z:z.writestr('Annotations/unknown.mat',mat({'x':1}))
    with pytest.raises(ValueError,match='unmatched'):ClassicVisionAdapter(prepared)._rows()


def test_gvil_pairs_keep_task_ids_answers_and_raw_annotations(tmp_path):
    import json
    path=tmp_path/'gvil.zip'
    rows={'a':{'img':'a.jpg','type':'samediff_qa','question':'Same?','answer_match':'yes','answer_mismatch':'no'},
          'b':{'img':'b.jpg','type':'samediff_qa','question':'Same?','answer_match':'no','answer_mismatch':'yes'}}
    vg={'a':{'img':'a.jpg','type':'localization','query':'left','bbox_match':[1,2,3,4],'bbox_mismatch':[4,3,2,1]},
        'b':{'img':'b.jpg','type':'localization','query':'right','bbox_match':[4,3,2,1],'bbox_mismatch':[1,2,3,4]}}
    with zipfile.ZipFile(path,'w') as z:
        for name,value in {'vqa_annotation.json':rows,'vg_annotation.json':vg,'pair_info.json':{'samediff_qa':[['a','b']],'localization':[['a','b']]},'raw_annotations.json':[{'img_file':'a.jpg','subjects':[]} ]}.items():z.writestr('dataset/'+name,json.dumps(value))
        for name in ['a.jpg','b.jpg']:z.writestr('dataset/images/'+name,b'fixture')
    adapter=ClassicVisionAdapter(Dataset(id='gvil',name='Fixture',release='r',snapshot_id='s',adapter='classic_vision',adapter_config={
        'path':str(path),'dataset_kind':'gvil','mapping':{'question':'question'}}))
    records=adapter.iter_records(adapter.prepare(adapter.plan(10,100000))).records
    assert len(records)==5 and len({r.id for r in records})==5
    vqa=[r for r in records if r.source['task']=='vqa'];vg=[r for r in records if r.source['task']=='vg']
    assert vqa[0].relations[0].object_id==vqa[1].id
    assert vg[0].relations[0].object_id==vg[1].id
    assert vqa[0].source['answer_match']=='yes' and vqa[0].question=='Same?'
    assert vqa[0].asset_ids==vg[0].asset_ids


def test_hod_joins_metadata_both_annotation_formats_and_duplicate_views(tmp_path):
    import zipfile
    from dataset_atlas.adapters.classic_vision import ClassicVisionAdapter
    from dataset_atlas.models import Dataset
    path = tmp_path/'hod.zip'
    xml = '<annotation><filename>a.jpg</filename><size><width>8</width><height>6</height></size><object><name>alcohol</name><bndbox><xmin>1</xmin><ymin>2</ymin><xmax>5</xmax><ymax>4</ymax></bndbox></object></annotation>'
    def write(changed=False):
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('release/dataset/metadata.csv', 'Category,Case Type,Image Name,Annotation Name (YOLOv5),Annotation Name (Faster R-CNN),Reference\nalcohol,Hard,a.jpg,a.txt,a.xml,https://source.example\n')
            for directory in ['all', 'class/alcohol/hard_cases']:
                for folder, name, value in [('jpg','a.jpg',b'image fixture'),('txt','a.txt','0 0.375 0.5 0.5 0.333333'),('xml','a.xml',xml)]:
                    if changed and directory!='all' and folder=='txt':value='1 0.375 0.5 0.5 0.333333'
                    z.writestr(f'release/dataset/{directory}/{folder}/{name}', value)
    write()
    ds = Dataset(id='hod', name='Fixture', release='r', snapshot_id='s', adapter='classic_vision', adapter_config={
        'path':str(path),'archive_prefix':'release/','dataset_kind':'hod'})
    adapter=ClassicVisionAdapter(ds)
    record=adapter.iter_records(adapter.prepare(adapter.plan(10,10000))).records[0]
    assert adapter.count==1 and record.source['difficulty']=='Hard'
    assert record.source['native_metadata']['Reference']=='https://source.example'
    assert record.source['xml_objects'][0]['box_xyxy']==[1,2,5,4]
    assert record.source['yolo_objects'][0]['class_name']=='alcohol'
    assert record.source['class_copy_members']['jpg'].endswith('class/alcohol/hard_cases/jpg/a.jpg')
    write(changed=True)
    with pytest.raises(ValueError,match='counterparts differ'):ClassicVisionAdapter(ds)._rows()
