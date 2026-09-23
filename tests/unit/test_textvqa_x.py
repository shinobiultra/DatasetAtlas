import hashlib,io,json,zipfile

import numpy as np
from PIL import Image
import pytest

from dataset_atlas.adapters.textvqa_x import TextVQAXAdapter
from dataset_atlas.models import Dataset


def make_adapter(tmp_path, array=None):
    files={'explanations_path':{'1':{'explanation':['synthetic'],'image':'fixture.jpg','Token':[['synthetic']]}},
           'questions_train_path':{'data':[{'question_id':1,'image_id':'fixture','question':'Synthetic question?'}]},
           'questions_val_path':{'data':[]},'train_ids_path':'1\n','val_ids_path':''}
    config={'annotations':[{'path_key':'explanations_path'}],'mapping':{'question':'_atlas_question'}}
    for key,value in files.items():
        path=tmp_path/key;path.write_text(value if isinstance(value,str) else json.dumps(value));config[key]=str(path)
    raw=io.BytesIO();np.save(raw,np.array([[True,False],[False,True]]) if array is None else array,allow_pickle=False)
    path=tmp_path/'masks.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('seg/1.npy',raw.getvalue())
    config.update(masks_path=str(path),local_archives={'masks':{'path_key':'masks_path'}},derived_archive_checksums={'masks_path':hashlib.sha256(path.read_bytes()).hexdigest()})
    return TextVQAXAdapter(Dataset(id='fixture',name='Synthetic fixture',release='test',adapter='textvqa_x',adapter_config=config)),raw.getvalue()


def test_native_array_and_lossless_preview_keep_original_values(tmp_path):
    adapter,native=make_adapter(tmp_path);source=adapter.prepare(adapter.plan(5,1_000_000))
    record=adapter.iter_records(source).records[0]
    assert record.question=='Synthetic question?' and [a.modality for a in record.assets]==['image','image','array']
    assert record.assets[1].representation=='lossless_mask_render'
    assert adapter.resolve_asset(source,'zip/masks/seg/1.npy').data==native
    rendered=adapter.resolve_asset(source,'mask/1.png')
    with Image.open(io.BytesIO(rendered.data)) as image:
        assert image.size==(2,2) and np.array_equal(np.asarray(image),np.load(io.BytesIO(native),allow_pickle=False))
    with pytest.raises(ValueError,match='outside'):
        adapter.resolve_asset(source,'mask/2.png')


def test_mask_type_and_native_split_joins_fail_closed(tmp_path):
    adapter,_=make_adapter(tmp_path,np.zeros((2,2),dtype=np.float64));source=adapter.prepare(adapter.plan(5,1_000_000))
    with pytest.raises(ValueError,match='boolean'):
        adapter.resolve_asset(source,'mask/1.png')
    adapter,_=make_adapter(tmp_path)
    from pathlib import Path
    Path(adapter.config['val_ids_path']).write_text('1\n')
    with pytest.raises(ValueError,match='repeated'):
        adapter._rows()
