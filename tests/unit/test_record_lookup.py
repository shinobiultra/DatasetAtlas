"""Record lookup parses each pack once per on-disk revision.

A selection resolves every ID in turn; re-parsing the pack per ID made a
100-record selection take over a second on the live workbench.
"""
from fastapi.testclient import TestClient

from dataset_atlas.api.app import create_app
from dataset_atlas import models


def test_records_endpoint_parses_pack_once_for_many_ids(workspace, monkeypatch):
    calls = []
    original = models.Pack.model_validate_json.__func__

    def counting(cls, *args, **kwargs):
        calls.append(1)
        return original(cls, *args, **kwargs)

    monkeypatch.setattr(models.Pack, 'model_validate_json', classmethod(counting))
    app = create_app(workspace)
    with TestClient(app, headers={'X-Atlas-Request': '1'}) as client:
        ids = ['r0', 'r1', 'r2', 'r3']
        first = client.post('/api/v1/records', json={'ids': ids})
        assert first.status_code == 200, first.text
        assert [record['id'] for record in first.json()] == ids
        parses_after_first = len(calls)
        second = client.post('/api/v1/records', json={'ids': list(reversed(ids))})
        assert second.status_code == 200
        assert [record['id'] for record in second.json()] == list(reversed(ids))
    # The registry's own load plus at most one parse for the lookup index — never one per ID.
    assert parses_after_first <= 2, parses_after_first
    assert len(calls) == parses_after_first


def test_records_endpoint_sees_a_rewritten_pack(workspace):
    app = create_app(workspace)
    with TestClient(app, headers={'X-Atlas-Request': '1'}) as client:
        before = client.post('/api/v1/records', json={'ids': ['r0']}).json()[0]['text']
        path = workspace / 'work/packs/fixture/pack.json'
        import json, os, time
        document = json.loads(path.read_text())
        document['records'][0]['text'] = 'rewritten on disk'
        path.write_text(json.dumps(document))
        os.utime(path, (time.time() + 5, time.time() + 5))
        after = client.post('/api/v1/records', json={'ids': ['r0']}).json()[0]['text']
    assert before == 'Text 0' and after == 'rewritten on disk'


def test_plan_endpoint_rejects_unknown_fields_and_non_integers(workspace):
    with TestClient(create_app(workspace), headers={'X-Atlas-Request': '1'}) as client:
        extra = client.post('/api/v1/datasets/fixture/preparation/plan', json={'max_download_bytes': 10, 'max_output_bytes': 10, 'surprise': 1})
        assert extra.status_code == 422
        fractional = client.post('/api/v1/datasets/fixture/preparation/plan', json={'max_download_bytes': 10.5, 'max_output_bytes': 10})
        assert fractional.status_code == 422
        missing = client.post('/api/v1/datasets/fixture/preparation/plan', json={'max_download_bytes': 10})
        assert missing.status_code == 422


def test_records_lookup_does_not_sweep_the_catalogue_per_id(workspace, monkeypatch):
    """A namespaced record ID resolves through its own dataset, not 336 stat calls per ID."""
    from dataset_atlas import registry as registry_module
    sweeps = []
    original = registry_module.Registry.datasets

    def counting(self):
        sweeps.append(1)
        return original(self)

    monkeypatch.setattr(registry_module.Registry, 'datasets', counting)
    app = create_app(workspace)
    with TestClient(app, headers={'X-Atlas-Request': '1'}) as client:
        sweeps.clear()
        response = client.post('/api/v1/records', json={'ids': ['r0', 'r1', 'r2', 'r3']})
        assert response.status_code == 200, response.text
    # Even unprefixed fixture IDs must not pay for resolving every dataset's active version.
    assert not sweeps, sweeps


def test_registry_recheck_window_still_sees_edits_after_refresh(workspace):
    import time
    import yaml
    from dataset_atlas.registry import Registry
    registry = Registry(workspace)
    assert registry.dataset('fixture').name == 'Test only'
    path = workspace / 'registry/datasets/fixture.yaml'
    document = yaml.safe_load(path.read_text()); document['name'] = 'Renamed'
    path.write_text(yaml.safe_dump(document))
    import os
    os.utime(path, (time.time() + 5, time.time() + 5))
    registry.refresh()
    assert registry.dataset('fixture').name == 'Renamed'


def test_versions_memo_reflects_a_new_active_version(workspace):
    import json
    from dataset_atlas.registry import Registry
    registry = Registry(workspace)
    before = registry.versions('fixture')
    assert len(before) == 1
    version = workspace / 'work/prepared/fixture/v1'
    (version / 'pack').mkdir(parents=True)
    dataset = json.loads(json.dumps(registry.dataset('fixture').model_dump(mode='json')))
    dataset['snapshot_id'] = 'prepared-snapshot'
    (version / 'dataset.json').write_text(json.dumps(dataset))
    (version.parent / 'active.json').write_text(json.dumps({'version': 'v1'}))
    after = registry.versions('fixture')
    assert len(after) == 2 and after[0][0].snapshot_id == 'prepared-snapshot'
