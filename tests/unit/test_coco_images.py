import json,zipfile
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.coco_images import CocoImagesAdapter


def fixture(tmp_path,bad=False):
    path=tmp_path/'annotations.zip'
    image={'id':1,'file_name':'one.jpg','width':12,'height':8,'license':1}
    instance={'id':7,'image_id':99 if bad else 1,'category_id':1,'bbox':[0,0,3,4],'segmentation':[[0,0,3,0,3,4]],'iscrowd':0}
    category={'id':1,'name':'person'}
    base={'images':[image],'licenses':[{'id':1,'name':'original source terms'}]}
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('instances.json',json.dumps({**base,'annotations':[instance],'categories':[category]}))
        z.writestr('captions.json',json.dumps({**base,'annotations':[{'id':3,'image_id':1,'caption':'A person.'},{'id':4,'image_id':1,'caption':'Someone stands.'}]}))
        z.writestr('keypoints.json',json.dumps({**base,'annotations':[{'id':7,'image_id':1,'category_id':1,'keypoints':[1,2,2]}],'categories':[{**category,'keypoints':['nose']}]}))
        z.writestr('test.json',json.dumps({'images':[{**image,'id':2,'file_name':'two.jpg'}]}))
    config={'path':str(path),'mapping':{'text':'caption_text'},'annotations':[
        {'path_key':'path','split':'train','images_member':'instances.json','instances_member':'instances.json','captions_member':'captions.json','keypoints_member':'keypoints.json','media_archive':'train','media_prefix':'train'},
        {'path_key':'path','split':'test','images_member':'test.json','media_archive':'test','media_prefix':'test'}],
        'remote_archives':{'train':{'etag':'"train"'},'test':{'etag':'"test"'}}}
    return CocoImagesAdapter(Dataset(id='coco-test',name='COCO test',release='r',snapshot_id='s',adapter='coco_images',adapter_config=config))


def test_full_annotations_preserved_and_withheld_different_from_zero(tmp_path):
    adapter=fixture(tmp_path);source=adapter.prepare(adapter.plan(5,100000));records=adapter.iter_records(source).records
    assert adapter.count==2
    train,test=records
    assert train.text=='A person.\nSomeone stands.'
    assert train.source['person_count']==1 and len(train.source['captions'])==2
    assert train.annotations[0].value['segmentation']==[[0,0,3,0,3,4]]
    assert train.annotations[0].subject_id==train.assets[0].id
    assert train.source['keypoints'][0]['keypoints']==[1,2,2]
    assert test.source['annotation_status']=='not_released'
    assert 'instances' not in test.source and 'person_count' not in test.source
    assert train.source['image_license']['name']=='original source terms'


def test_unmatched_annotation_rejected(tmp_path):
    with pytest.raises(ValueError,match='orphan'):fixture(tmp_path,True)._rows()
