"""Synthetic direct-source acquisition over the exact current recipe shapes."""
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from dataset_atlas.adapters import get_adapter
from dataset_atlas.models import Dataset, Pack
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run
from dataset_atlas.queries.parquet import ParquetSnapshot
from dataset_atlas.storage.sources import register_source

ROOT = Path(__file__).resolve().parents[2]
NAMES = ['advbench', 'harmbench', 'realtoxicityprompts']


def payload(name):
    if name == 'advbench':
        return b'goal,target\nSynthetic request A,Synthetic prefix A\nSynthetic request B,Synthetic prefix B\n'
    if name == 'harmbench':
        return b'BehaviorID,Behavior,FunctionalCategory,SemanticCategory,Tags,ContextString\ns1,Synthetic A,fixture,fixture,,\ns2,Synthetic B,fixture,fixture,,\n'
    return b'\n'.join(json.dumps({'prompt': {'text': f'Synthetic prompt {i}'}, 'continuation': {'text': 'Synthetic continuation'},
                                'challenging': bool(i), 'filename': 'synthetic', 'begin': i, 'end': i + 1}).encode()
                       for i in range(2)) + b'\n'


@pytest.mark.parametrize('name', NAMES)
def test_default_recipe_plans_cold_and_prepares_exact_source_without_activation(tmp_path, monkeypatch, name):
    document = yaml.safe_load((ROOT / 'registry/recipes' / (name + '.yaml')).read_text())
    baseline = yaml.safe_load((ROOT / 'registry/datasets' / (name + '.yaml')).read_text())
    # Fixtures keep the real parser/mapping, but never claim to be native releases.
    baseline.update(name='Synthetic acquisition fixture', release='synthetic-release', snapshot_id='synthetic-snapshot')
    data = payload(name)
    digest = hashlib.sha256(data).hexdigest()
    baseline['adapter_config'].update(path='work/absent-fixture-source', sha256=digest)
    document.update(release='synthetic-release', snapshot_id='synthetic-snapshot', expected_count=2)
    document['files'][0].update(bytes=len(data), sha256=digest)
    root = tmp_path / name
    for directory in ['registry/datasets', 'registry/recipes']:
        (root / directory).mkdir(parents=True)
    (root / 'registry/datasets' / (name + '.yaml')).write_text(yaml.safe_dump(baseline))
    (root / 'registry/recipes' / (name + '.yaml')).write_text(yaml.safe_dump(document))

    def no_network(*args, **kwargs):
        raise AssertionError('Synthetic planning/preparation must not access a network')

    monkeypatch.setattr('dataset_atlas.adapters.core.HTTPSStructuredAdapter.probe', no_network)
    monkeypatch.setattr('dataset_atlas.storage.https.HttpsFetcher.fetch', no_network)
    manager = PreparationManager(root)
    cold = manager.plan(name, len(data), 2_000_000)
    assert cold['ready'] and cold['kind'] == 'http_archive'
    assert cold['expected_count'] == 2 and cold['expected_download_bytes'] == len(data)
    assert cold['recipe_snapshot_id'] == 'synthetic-snapshot'
    original = tmp_path / 'synthetic-original'
    original.write_bytes(data)
    register_source(root, original, digest, len(data))
    run(root, cold['id'], activate=False)
    assert manager.status(cold['id'])['status'] == 'completed'
    version = root / 'work/prepared' / name / cold['id']
    receipt = json.loads((version / 'receipt.json').read_text())
    assert receipt['total_transfer_bytes'] == 0 and receipt['registered_source_reused_bytes'] == len(data)
    assert not (version.parent / 'active.json').exists()
    control = Dataset.model_validate(baseline)
    control.adapter = 'structured'
    control.adapter_config['path'] = str(original)
    adapter = get_adapter(control)
    expected = adapter.iter_records(adapter.prepare(adapter.plan(100, 2_000_000))).records
    snapshot = ParquetSnapshot(root, version / 'snapshot')
    assert snapshot.record_count == 2 and snapshot.snapshot_id == control.snapshot_id
    stored = snapshot.records([record.id for record in expected])
    assert list(stored.values()) == expected
    pack = Pack.model_validate_json((version / 'pack/pack.json').read_text())
    assert {record.id for record in pack.records} == {record.id for record in expected}
    assert original.read_bytes() == data


@pytest.mark.parametrize('name', NAMES)
def test_recipe_preserves_registered_release_snapshot_and_native_mapping(name):
    baseline = yaml.safe_load((ROOT / 'registry/datasets' / (name + '.yaml')).read_text())
    document = yaml.safe_load((ROOT / 'registry/recipes' / (name + '.yaml')).read_text())
    config = baseline['adapter_config']
    assert document['release'] == baseline['release']
    assert document['snapshot_id'] == baseline['snapshot_id']
    assert document['expected_count'] == baseline['coverage']['total_count']
    assert document['files'][0]['url'] == config['url']
    assert document['files'][0]['sha256'] == config['sha256']
    assert document['files'][0]['config_key'] == 'path'
    assert document['adapter_config']['mapping'] == config['mapping']
