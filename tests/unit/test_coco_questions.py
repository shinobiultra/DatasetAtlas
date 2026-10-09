import io,json,zipfile
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters.coco_questions import CocoQuestionsAdapter


def make_adapter(tmp_path,monkeypatch,kind='vqa',bad=None):
    path=tmp_path/'annotations.zip'
    with zipfile.ZipFile(path,'w') as archive:
        if kind=='vqa':
            questions=[{'question_id':5,'image_id':42,'question':'What?'},{'question_id':6,'image_id':42,'question':'Where?'}]
            annotations=[{'question_id':5,'image_id':42,'answers':[{'answer':'cat','answer_confidence':'yes'}]},{'question_id':6,'image_id':42,'answers':[]}]
            if bad=='missing':annotations.pop()
            if bad=='image':annotations[0]['image_id']=7
            if bad=='duplicate':annotations.append(annotations[0])
            if bad=='orphan':annotations.append({'question_id':7,'image_id':42})
            archive.writestr('q.json',json.dumps({'questions':questions}));archive.writestr('a.json',json.dumps({'annotations':annotations}))
            entries=[{'split':'train','questions_path_key':'path','questions_member':'q.json','answers_path_key':'path','answers_member':'a.json','media_archive':'train2014','media_prefix':'train2014'}]
        else:
            for name,contents in {'questions':'What?\nWhere?\n','answers':'cat\nhome\n','img_ids':'42\n42\n','types':'0\n3\n'}.items():
                archive.writestr('train/'+name+'.txt',contents if bad!='length' or name!='types' else '0\n')
            entries=[{'split':'train','path_key':'path','prefix':'train'}]
    media=io.BytesIO()
    with zipfile.ZipFile(media,'w') as archive:archive.writestr('train2014/COCO_train2014_000000000042.jpg',b'fixture')
    class Remote(io.BytesIO):bytes_fetched=100
    monkeypatch.setattr(CocoQuestionsAdapter,'_remote',lambda self,key,budget:Remote(media.getvalue()))
    return CocoQuestionsAdapter(Dataset(id='coco-test',name='Test',release='r',snapshot_id='s',adapter='coco_questions',adapter_config={
        'dataset_kind':kind,'path':str(path),'annotations':entries,'mapping':{'question':'question'},'remote_archives':{'train2014':{'etag':'"test"'}}}))


@pytest.mark.parametrize('kind',['vqa','cocoqa'])
def test_native_question_join_preserves_answers_ids_and_shared_images(tmp_path,monkeypatch,kind):
    adapter=make_adapter(tmp_path,monkeypatch,kind)
    assert adapter.probe().exists
    source=adapter.prepare(adapter.plan(1,100000));first=adapter.iter_records(source);second=adapter.iter_records(source,first.next_cursor)
    assert first.records[0].id!=second.records[0].id
    assert first.records[0].asset_ids==second.records[0].asset_ids
    assert second.records[0].question=='Where?'
    if kind=='vqa':assert first.records[0].source['annotation']['answers'][0]['answer_confidence']=='yes'
    else:assert second.records[0].source['type_name']=='location'
    assert adapter.validate_media(10000)['referenced_images']==1
    assert adapter.count==2


@pytest.mark.parametrize('bad,match',[('missing','Missing answer'),('image','image ID mismatch'),('duplicate','Duplicate annotation'),('orphan','Orphan answer')])
def test_native_vqa_rejects_broken_joins(tmp_path,monkeypatch,bad,match):
    with pytest.raises(ValueError,match=match):make_adapter(tmp_path,monkeypatch,bad=bad)._rows()


def test_line_alignment_must_be_exact(tmp_path,monkeypatch):
    with pytest.raises(ValueError,match='different lengths'):make_adapter(tmp_path,monkeypatch,'cocoqa','length')._rows()
