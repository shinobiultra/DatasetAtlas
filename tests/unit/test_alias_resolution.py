"""Explicit aliases belong to live datasets and cannot shadow other entries."""
import yaml
import httpx
import pytest
from dataset_atlas.api import create_app
from dataset_atlas.registry import Registry

def _write(root, dataset):
    (root / 'registry/datasets').mkdir(parents=True, exist_ok=True)
    (root / 'registry/datasets' / f"{dataset['id']}.yaml").write_text(yaml.safe_dump(dataset))


def test_declared_aliases_resolve_without_shadowing_live_ids_or_ambiguous_names(tmp_path):
    _write(tmp_path, {'id': 'canon', 'name': 'Canon', 'release': 'r', 'snapshot_id': 's',
                      'aliases': ['friendly-name', 'live', 'shared-name', 'friendly-name'],
                      'relationships': [{'type': 'source_subset_of', 'target_id': 'source-view'}]})
    _write(tmp_path, {'id': 'live', 'name': 'Live', 'release': 'r', 'snapshot_id': 's',
                     'aliases': ['shared-name']})
    registry = Registry(tmp_path)
    assert registry.resolve('friendly-name') == 'canon'
    assert registry.dataset('friendly-name').id == 'canon'
    assert registry.resolve('live') == 'live' and registry.dataset('live').id == 'live'
    assert registry.resolve('shared-name') == 'shared-name'
    assert registry.resolve('source-view') == 'source-view'
    assert registry.resolve('missing') == 'missing'
    assert not registry.has('friendly-name')  # aliases are not catalogue entries
    assert [d.id for d in registry.datasets()] == ['canon', 'live']


@pytest.mark.asyncio
async def test_declared_alias_resolves_over_the_api_without_a_history_file(tmp_path):
    _write(tmp_path, {'id': 'canon', 'name': 'Canon', 'aliases': ['friendly-name']})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(tmp_path)),
                                 base_url='http://testserver') as client:
        response = await client.get('/api/v1/datasets/friendly-name')
        assert response.status_code == 200
        assert response.json()['id'] == 'canon'
        assert response.json()['aliases'] == ['friendly-name']
        assert (await client.get('/api/v1/datasets/never-existed')).status_code == 404


def test_refresh_removes_aliases_when_their_dataset_leaves_the_registry(tmp_path):
    _write(tmp_path, {'id': 'canon', 'name': 'Canon', 'aliases': ['friendly-name']})
    registry = Registry(tmp_path)
    assert registry.resolve('friendly-name') == 'canon'
    (tmp_path / 'registry/datasets/canon.yaml').unlink()
    registry.refresh()
    assert registry.resolve('friendly-name') == 'friendly-name'
    assert registry.datasets() == []
