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
