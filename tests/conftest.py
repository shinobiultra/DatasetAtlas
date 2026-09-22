import json
import pytest
import yaml
from dataset_atlas.models import Dataset, Coverage, Asset, Record, Pack, FieldDescriptor, Annotation, Relation, stable_id

@pytest.fixture
def pack():
    dataset=Dataset(id='fixture',name='Test only',release='r1',snapshot_id='s1',coverage=Coverage(identity='resolved',access='locally_supplied',preview_count=4))
    asset=Asset(id='asset-1',dataset_id='fixture',release_id='r1',modality='image',uri='media/test.png')
    records=[]
    for index,(label,score) in enumerate([('A',1),('B',2),('A',None),(None,4)]):
        records.append(Record(id=f'r{index}',dataset_id='fixture',release_id='r1',snapshot_id='s1',text=f'Text {index}',question='Which object?',asset_ids=[asset.id],assets=[asset],source={'label':label,'score':score},annotations=[Annotation(id=f'a{index}',subject_id=f'r{index}',subject_unit='example',field_id='source.label',value=label)],relations=[Relation(subject_id=f'r{index}',object_id='r0',type='same_asset')]))
    return Pack(dataset=dataset,fields=[FieldDescriptor(id='source.label',name='Label',dtype='category'),FieldDescriptor(id='source.score',name='Score',dtype='number')],records=records,sampling={'method':'source','population':'test fixture only'})

@pytest.fixture
def workspace(tmp_path,pack):
    (tmp_path/'registry/datasets').mkdir(parents=True)
    (tmp_path/'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(pack.dataset.model_dump()))
    (tmp_path/'work/packs/fixture').mkdir(parents=True)
    (tmp_path/'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    return tmp_path

@pytest.fixture
def require_local_files():
    """Optional source acceptance checks run only where their acquisition exists.

    Missing inputs are explicit skips in clean CI, never evidence of validation.
    Once the listed entry points exist, all content/hash assertions still run.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    def require(*names):
        absent = [name for name in names if not (root / name).is_file()]
        if absent:
            pytest.skip("Optional acquired local inputs are absent: " + ", ".join(absent))
    return require
