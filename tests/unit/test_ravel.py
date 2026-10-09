import io
import json
import tarfile
import pytest
from dataset_atlas.models import Dataset
from dataset_atlas.adapters import get_adapter


def fixture(tmp_path, missing_split=False):
    path = tmp_path / 'data.tgz'
    documents = {
        'ravel_city_entity_attributes': {'City A': {'Country': 'Country B'}},
        'ravel_city_entity_to_split': {} if missing_split else {'City A': 'train'},
        'ravel_city_attribute_to_prompts': {'Country': ['%s is in'], 'Control': ['%s might']},
        'ravel_city_prompt_to_split': {'%s is in': 'test', '%s might': 'val'},
        'wikipedia_city_entity_prompts': {'%s, a place': {'entity': 'Other city', 'split': 'test'}},
    }
    with tarfile.open(path, 'w:gz') as archive:
        for name, value in documents.items():
            data = json.dumps(value).encode(); info = tarfile.TarInfo('data/' + name + '.json'); info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return get_adapter(Dataset(id='ravel', name='Fixture', release='r', snapshot_id='s', adapter='ravel',
        adapter_config={'path': str(path), 'domains': ['city']}))


def test_native_ravel_keeps_independent_populations_and_missing_ground_truth(tmp_path):
    adapter = fixture(tmp_path)
    records = adapter.iter_records(adapter.prepare(adapter.plan(10, 100000))).records
    assert len(records) == 2
    entity, control = records
    assert entity.text == 'City A' and entity.source['attributes'] == {'Country': 'Country B'}
    assert entity.source['attributes_without_released_values'] == ['Control']
    assert entity.source['attribute_templates']['Country'][0]['split'] == 'test'
    assert entity.source['entity_split'] == 'train'
    assert control.source['record_kind'] == 'wikipedia_prompt'
    assert control.source['entity_in_attribute_inventory'] is False
    assert control.text == '%s, a place'
    assert entity.id != control.id


def test_ravel_rejects_inconsistent_split_inventory(tmp_path):
    with pytest.raises(ValueError, match='split inventory'):
        fixture(tmp_path, missing_split=True)._rows()
