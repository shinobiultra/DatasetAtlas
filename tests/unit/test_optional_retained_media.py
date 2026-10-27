"""Synthetic optional-original tests; real native coverage has separate receipts."""
import hashlib
import io
import json

from PIL import Image
import pytest
import yaml

from dataset_atlas.models import Dataset
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run


def fixture(root):
    annotation=root/'native.json'
    annotation.write_text(json.dumps([{'image':'first.png','question':'Synthetic first?','candidates':['a','b']},
                                      {'image':'second.png','question':'Synthetic second?','candidates':['b','a']}]))
    bindings={};payloads={}
    for name,color in [('first.png','red'),('second.png','blue')]:
        buffer=io.BytesIO();Image.new('RGB',(3,2),color).save(buffer,'PNG');data=buffer.getvalue()
        sha=hashlib.sha256(data).hexdigest();payloads[sha]=data
        bindings[json.dumps(['task',name],separators=(',',':'))]={'path':sha,'sha256':sha,'bytes':len(data)}
    dataset=Dataset(id='optional-fixture',name='Synthetic fixture',release='r',adapter='structured_collection',
                    coverage={'total_count':2})
    registry=root/'registry/datasets';registry.mkdir(parents=True)
    (registry/'optional-fixture.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    recipe={'expected_count':2,'scope':'Two synthetic native question rows','adapter_config':{
        'path':str(annotation),'annotations':[{'path_key':'path','split':'task','choices_field':'candidates',
            'unavailable_media':{'path_field':'image','modality':'image','availability':'not_acquired'}}],
        'mapping':{'question':'question','choices':'_atlas_choices'},'media_scope':'partial',
        'retained_media_root':'work/source-objects','retained_media':bindings,
        'retained_media_optional':True,'retained_media_max_bytes':10000}}
    recipes=root/'registry/recipes';recipes.mkdir(parents=True)
    (recipes/'optional-fixture.yaml').write_text(yaml.safe_dump(recipe))
    return PreparationManager(root),payloads


def test_missing_optional_store_yields_complete_metadata_index(tmp_path):
    manager,_=fixture(tmp_path);plan=manager.plan('optional-fixture',10000,1_000_000)
    config=plan['prepared_dataset']['adapter_config']
    assert plan['ready'] and config['retained_media']=={} and config['retained_media_optional'] is False
    run(tmp_path,plan['id'],activate=False)
    directory=tmp_path/'work/prepared/optional-fixture'/plan['id']
    dataset=json.loads((directory/'dataset.json').read_text());pack=json.loads((directory/'pack/pack.json').read_text())
    assert dataset['coverage']['total_count']==2 and dataset['coverage']['preview']=='metadata_only'
    assert dataset['coverage']['complete_data']=='indexed_metadata_partial_media'
    assert len(pack['records'])==2 and all(asset['uri'] is None for row in pack['records'] for asset in row['assets'])
    assert [row['choices'] for row in pack['records']].count(['a','b'])==1


def test_optional_presence_is_frozen_into_plan_and_changed_original_fails(tmp_path):
    manager,payloads=fixture(tmp_path);absent=manager.plan('optional-fixture',10000,1_000_000)
    sha,data=next(iter(payloads.items()));library=tmp_path/'work/source-objects';library.mkdir(parents=True)
    original=library/sha;original.write_bytes(data)
    present=manager.plan('optional-fixture',10000,1_000_000)
    assert present['id']!=absent['id']
    assert len(present['prepared_dataset']['adapter_config']['retained_media'])==1
    # A file appearing after an absent plan does not silently change that plan.
    run(tmp_path,absent['id'],activate=False)
    absent_pack=json.loads((tmp_path/'work/prepared/optional-fixture'/absent['id']/'pack/pack.json').read_text())
    assert all(asset['uri'] is None for row in absent_pack['records'] for asset in row['assets'])
    original.write_bytes(b'changed')
    with pytest.raises(ValueError,match='checksum or size'):
        run(tmp_path,present['id'],activate=False)
    with pytest.raises(ValueError,match='checksum or size'):
        manager.plan('optional-fixture',10000,1_000_000)
