"""Retired alias IDs resolve to their canonical catalogue entry instead of 404ing."""
from pathlib import Path
import yaml
from fastapi.testclient import TestClient
from dataset_atlas.api import create_app
from dataset_atlas.registry import Registry

ROOT = Path(__file__).resolve().parents[2]


def _write(root, dataset):
    (root / 'registry/datasets').mkdir(parents=True, exist_ok=True)
    (root / 'registry/datasets' / f"{dataset['id']}.yaml").write_text(yaml.safe_dump(dataset))


def test_redirects_and_relationships_both_resolve_without_shadowing_live_ids(tmp_path):
    _write(tmp_path, {'id': 'canon', 'name': 'Canon', 'release': 'r', 'snapshot_id': 's',
                      'relationships': [{'type': 'alias_resolved_from', 'target_id': 'old-name', 'status': 'confirmed'}]})
    _write(tmp_path, {'id': 'live', 'name': 'Live', 'release': 'r', 'snapshot_id': 's'})
    (tmp_path / 'registry/candidate_dispositions.yaml').write_text(yaml.safe_dump({'alias_redirects': [
        {'alias_id': 'older-name', 'canonical_id': 'canon', 'disposition': 'confirmed_same_release_alias'},
        {'alias_id': 'live', 'canonical_id': 'canon', 'disposition': 'confirmed_same_release_alias'},   # must not shadow
        {'alias_id': 'ghost', 'canonical_id': 'missing', 'disposition': 'confirmed_same_release_alias'},  # no invented dataset
    ]}))
    registry = Registry(tmp_path)
    assert registry.resolve('old-name') == 'canon'
    assert registry.resolve('older-name') == 'canon'
    assert registry.dataset('older-name').id == 'canon'
    assert registry.resolve('live') == 'live' and registry.dataset('live').id == 'live'
    assert registry.resolve('ghost') == 'ghost'
    assert not registry.has('old-name')  # aliases are not catalogue entries
    assert [d.id for d in registry.datasets()] == ['canon', 'live']


def test_repository_retired_ids_resolve_over_the_api():
    client = TestClient(create_app(ROOT))
    for retired, canonical in (('pets', 'oxfordpet'), ('describable-textures-dataset', 'dtd'), ('okvqa', 'ok-vqa')):
        response = client.get(f'/api/v1/datasets/{retired}')
        assert response.status_code == 200, (retired, response.text[:200])
        assert response.json()['id'] == canonical
        assert retired in response.json()['aliases']
    assert client.get('/api/v1/datasets/never-existed').status_code == 404
