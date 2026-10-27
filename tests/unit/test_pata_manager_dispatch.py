"""PATA's ordinary preparation route, using synthetic native-file layouts."""
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from dataset_atlas.models import Dataset, Pack
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run


def seeded_workspace(tmp_path, monkeypatch):
    import dataset_atlas.preparation.pata as module
    revision = 'synthetic-pata-revision'
    monkeypatch.setattr(module, 'REVISION', revision)
    source = tmp_path / 'work/sources/pata' / revision
    source.mkdir(parents=True)
    files = source / 'synthetic.lst'
    captions = source / 'synthetic.json'
    files.write_text('scene_R_G_A|https://example.test/synthetic.jpg\n' * 4934)
    captions.write_text(json.dumps([{'short': 'scene', 'long': 'Synthetic caption', 'pos': {}, 'neg': {}}]))
    monkeypatch.setattr(module, 'SOURCES', {
        key: (path.name, hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size)
        for key, path in [('files', files), ('captions', captions)]})
    registry = tmp_path / 'registry/datasets'
    registry.mkdir(parents=True)
    dataset = Dataset(id='pata', name='Synthetic PATA manager fixture')
    (registry / 'pata.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    return module


def test_cold_pata_plan_uses_fixed_builtin_source_and_normal_budget_admission(tmp_path):
    registry = tmp_path / 'registry/datasets'
    registry.mkdir(parents=True)
    (registry / 'pata.yaml').write_text(yaml.safe_dump(Dataset(id='pata', name='PATA fixture').model_dump(mode='json')))
    manager = PreparationManager(tmp_path)
    plan = manager.plan('pata', 1_000_000, 20_000_000)
    assert plan['ready'] and plan['kind'] == 'pata_metadata'
    assert plan['expected_count'] == 4934 and plan['preview_count'] == 100
    assert plan['expected_download_bytes'] == 759949
    assert len(plan['builtin_source']['files']) == 2
    assert len(plan['files']) == 2
    assert plan['resource_limits']['max_wall_seconds'] <= 120
    too_small = manager.plan('pata', 100, 20_000_000)
    assert not too_small['ready']
    no_output = manager.plan('pata', 1_000_000, 100)
    assert not no_output['ready']


@pytest.mark.parametrize('activate', [False, True])
def test_normal_worker_prepares_exact_metadata_without_nested_writer_lock(tmp_path, monkeypatch, activate):
    seeded_workspace(tmp_path, monkeypatch)
    manager = PreparationManager(tmp_path)
    plan = manager.plan('pata', 1_000_000, 20_000_000)
    assert plan['ready']
    run(tmp_path, plan['id'], activate=activate)
    state = manager.status(plan['id'])
    assert state['status'] == 'completed' and state['activate_on_success'] is activate
    directory = tmp_path / 'work/prepared/pata' / plan['id']
    pack = Pack.model_validate_json((directory / 'pack/pack.json').read_text())
    receipt = json.loads((directory / 'receipt.json').read_text())
    assert len(pack.records) == 100 and pack.dataset.coverage.preview == 'metadata_only'
    assert all(not record.assets and record.source['media_available'] is False for record in pack.records)
    assert all(record.source['captions']['long'] == 'Synthetic caption' for record in pack.records)
    assert receipt['plan_id'] == plan['id'] and receipt['record_count'] == 4934
    assert receipt['total_transfer_bytes'] == 0 and receipt['native_image_preview_count'] == 0
    assert receipt['exact_native_record_checks'] == 4934
    assert (directory.parent / 'active.json').exists() is activate


def test_worker_rejects_a_changed_builtin_contract_before_preparation(tmp_path, monkeypatch):
    module = seeded_workspace(tmp_path, monkeypatch)
    manager = PreparationManager(tmp_path)
    plan = manager.plan('pata', 1_000_000, 20_000_000)
    assert plan['ready']
    monkeypatch.setattr(module, 'REVISION', 'different-synthetic-revision')
    with pytest.raises(ValueError, match='contract'):
        run(tmp_path, plan['id'], activate=False)
    assert manager.status(plan['id'])['status'] == 'failed'
    assert not (tmp_path / 'work/prepared/pata/active.json').exists()
