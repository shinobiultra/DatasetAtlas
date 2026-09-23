import hashlib
import json

import pytest

from dataset_atlas.adapters.phantom import PhantomAdapter
from dataset_atlas.models import Dataset


def fixture(tmp_path):
    common = dict(id='a', goal='Fixture goal', target_model='fixture', main_category='Category',
                  subcategory='Subcategory', strategy='fixture', number_of_steps=2)
    turns = [{**common, 'step': step, 'prompt': f'Fixture turn {step}', 'file_name': path}
             for step, path in [(1, 'present.png'), (2, 'missing.png')]]
    attack = {**common, 'conversation': {str(t['step']): {'prompt': t['prompt'], 'image': 'old/' + t['file_name']} for t in turns}}
    extra = {**turns[0], 'id': 'b', 'number_of_steps': 1}
    behaviour = dict(id=1, original_prompt='Fixture intent', image_path=[], benchmark='PHANTOM', embedding=None)
    values = {'phantom_attacks_json': [{'attack': attack}], 'metadata_jsonl': turns + [extra],
              'phantom_behaviours_json': [behaviour], 'behaviours_jsonl': [{k: v for k, v in behaviour.items() if k != 'embedding'}]}
    values['behaviours_jsonl'][0]['image_path'] = ''
    config = {'population': 'all', 'annotations': []}
    for key, value in values.items():
        path = tmp_path/key
        path.write_text('\n'.join(json.dumps(v) for v in value) if key.endswith('jsonl') else json.dumps(value))
        config[key] = str(path)
        config['annotations'].append({'path_key': key})
    inventory = tmp_path/'inventory.json'
    inventory.write_text(json.dumps({'files': {'present.png': {'bytes': 10, 'sha256': 'a'*64}}}))
    config.update(media_inventory_path=str(inventory), media_inventory_sha256=hashlib.sha256(inventory.read_bytes()).hexdigest())
    return PhantomAdapter(Dataset(id='phantom', name='Fixture', release='r', snapshot_id='s', adapter='phantom', adapter_config=config))


def test_conversation_join_retains_discrepancies_and_unavailable_assets(tmp_path):
    adapter = fixture(tmp_path)
    source = adapter.prepare(adapter.plan(10, 100000))
    records = adapter.iter_records(source).records
    assert len(records) == 3 and len({r.id for r in records}) == 3
    first, extra, behaviour = records
    assert first.unit == 'example' and first.source['_atlas_example_kind'] == 'conversation' and len(first.conversation) == 2
    assert first.assets[0].uri == 'file/present.png'
    assert first.assets[1].uri is None and first.assets[1].metadata['availability'] == 'absent_from_pinned_release'
    assert first.conversation[1]['asset_ids'] == [first.assets[1].id]
    assert first.source['native_attack']['conversation']['1']['image'] == 'old/present.png'
    assert extra.source['native_attack'] is None and extra.source['_atlas_source_status'] == 'Only released in metadata.jsonl'
    assert not behaviour.assets and behaviour.text == 'Fixture intent'
    assert adapter.validate_media(1000)['referenced_images'] == 1
    adapter = fixture(tmp_path)
    adapter.config['population'] = 'child_safety_behaviours'
    assert adapter.count == 1


def test_disagreeing_turn_content_fails_instead_of_silent_replacement(tmp_path):
    adapter = fixture(tmp_path)
    from pathlib import Path
    path = Path(adapter.config['metadata_jsonl'])
    path.write_text(path.read_text().replace('Fixture turn 2', 'Changed turn'))
    with pytest.raises(ValueError, match='content differ'):
        adapter._rows()
