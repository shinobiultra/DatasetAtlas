import json
from pathlib import Path

from dataset_atlas.adapters.pathways import PathwaysAdapter
from dataset_atlas.models import Dataset


def adapter(tmp_path, split, rows):
    path = tmp_path/'synthetic.json'
    path.write_text(json.dumps(rows))
    return PathwaysAdapter(Dataset(id='fixture',name='Synthetic Pathways fixture',adapter='pathways',release='fixture',
        adapter_config={'pathways_split':split,'path':str(path),'annotations':[{'path_key':'path','split':split,
            'choices_field':'caption_options','media_paths_field':'image_path'}]}))


def test_author_vg_two_exclusion_and_native_provenance(tmp_path):
    native={'caption_options':['A photo of a cube above a ball','A photo of a cube below a ball'],'image_path':'1.jpg'}
    value=adapter(tmp_path,'vg_qa_two',[{'caption_options':['unparseable','wrong'],'image_path':'0.jpg'},native])
    rows=value._rows()
    assert len(rows)==1 and rows[0]['_atlas_origin']['row']==1
    assert rows[0]['caption_options']==native['caption_options']
    assert rows[0]['_atlas_pathways']['objects']==['cube','ball']
    assert rows[0]['_atlas_pathways']['preposition']=='above'
    assert value._rows()==rows
    assert len(adapter(tmp_path,'coco_two',[{'caption_options':['unparseable','wrong'],'image_path':'0.jpg'}])._rows())==1


def test_controlled_and_one_object_author_parsing(tmp_path):
    value=adapter(tmp_path,'controlled_images',[{'caption_options':['right','wrong'],'image_path':'data/red-cube_right_of_blue-ball.jpeg'}])
    fields=value._rows()[0]['_atlas_pathways']
    assert fields['objects']==['red cube','blue ball'] and fields['preposition']=='right'
    value=adapter(tmp_path,'coco_one',[{'caption_options':['A photo of a ball on the left side','wrong'],'image_path':'0.jpg'}])
    assert value._rows()[0]['_atlas_pathways']['preposition']=='left'
