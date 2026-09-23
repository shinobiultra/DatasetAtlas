import hashlib
import io
import zipfile

import numpy as np
import pytest
from PIL import Image

from dataset_atlas.adapters.perceptual import PerceptualAdapter
from dataset_atlas.models import Dataset


def fixture(tmp_path, missing=False, invalid=False):
    picture=io.BytesIO();Image.new('RGB',(4,4),'white').save(picture,format='PNG')
    archives={};config={'annotations':[],'source_files':[]}
    for task,roles in [('2afc',['ref','p0','p1']),('jnd',['p0','p1'])]:
        name=tmp_path/(task+'.zip');judgement=io.BytesIO();np.save(judgement,np.array([2 if invalid else .6],dtype=np.float32))
        with zipfile.ZipFile(name,'w') as z:
            for role in roles:
                if not (missing and role=='p1'):z.writestr('val/cnn/'+role+'/001.png',picture.getvalue())
            z.writestr('val/cnn/'+('judge' if task=='2afc' else 'same')+'/001.npy',judgement.getvalue())
        key=task+'_path';config[key]=str(name);config['annotations'].append({'path_key':key});config['source_files'].append({'path':str(name),'sha256':hashlib.sha256(name.read_bytes()).hexdigest()});archives[task]={'path_key':key,'task':task}
    config['local_archives']=archives
    return PerceptualAdapter(Dataset(id='bapps',name='Fixture',release='r',snapshot_id='s',adapter='perceptual',adapter_config=config))


def test_native_patch_roles_and_fractional_human_judgements_are_preserved(tmp_path):
    adapter=fixture(tmp_path);source=adapter.prepare(adapter.plan(10,100000));rows=adapter.iter_records(source).records
    assert len(rows)==2 and rows[0].id!=rows[1].id
    assert [a.metadata['source_role'] for a in rows[0].assets]==['ref','p0','p1']
    assert [a.metadata['source_role'] for a in rows[1].assets]==['p0','p1']
    assert rows[0].source['judgement']==pytest.approx(.6) and rows[0].source['native_judgement_dtype']=='float32'
    assert adapter.validate_media(100000)['referenced_images']==5
    assert adapter.resolve_asset(source,rows[0].assets[0].uri).media_type=='image/png'


def test_missing_patches_and_invalid_labels_are_not_silently_dropped(tmp_path):
    with pytest.raises(ValueError,match='missing patch'):fixture(tmp_path,missing=True)._rows()
    with pytest.raises(ValueError,match='outside'):fixture(tmp_path,invalid=True)._rows()
