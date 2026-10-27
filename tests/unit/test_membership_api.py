"""Synthetic HTTP checks for query-aligned map membership and small browse payloads."""
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import yaml

from dataset_atlas.api.app import create_app
from dataset_atlas.models import Artifact, Dataset, FieldDescriptor, Pack, Record


@pytest.fixture
def root(tmp_path: Path):
    dataset = Dataset(id='toy', name='Synthetic only', release='r1', snapshot_id='s1')
    rows = [Record(id=f'row-{i}', dataset_id='toy', release_id='r1', snapshot_id='s1', text='keep' if i < 2 else 'other') for i in range(4)]
    projection = Artifact(id='projection', kind='projection.pca', unit='example', snapshot_ids=['s1'], ids=[r.id for r in rows],
                          data={'points': [{'id': r.id, 'x': i, 'y': i, 'z': i} for i, r in enumerate(rows)]})
    imported = Artifact(id='imported', kind='import.research', unit='example', snapshot_ids=['s1'], ids=[r.id for r in rows],
                        provenance={'processor_provenance': {'kind': 'vector', 'registered_embedding_space': True}},
                        data={'items': [{'id': r.id, 'status': 'completed', 'output': {'value': [1.0, 2.0], 'vector': [1.0, 2.0], 'label': 'kept'}} for r in rows]})
    pack = Pack(dataset=dataset, fields=[FieldDescriptor(id='text', name='Text', namespace='record')], records=rows,
                artifacts=[projection, imported], population_scope='preview', sampling={'method': 'source', 'size': 4})
    (tmp_path/'registry/datasets').mkdir(parents=True)
    (tmp_path/'registry/datasets/toy.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    (tmp_path/'work/packs/toy').mkdir(parents=True)
    (tmp_path/'work/packs/toy/pack.json').write_text(pack.model_dump_json())
    return tmp_path


def test_membership_http_filters_full_projection_and_binds_snapshot(root):
    with TestClient(create_app(root)) as client:
        query = {'snapshot_id': 's1', 'population_scope': 'preview', 'unit': 'example', 'search': 'keep', 'limit': 1}
        response = client.post('/api/v1/datasets/toy/membership/projection', json=query, headers={'X-Atlas-Request': '1'})
        assert response.status_code == 200, response.text
        assert response.content == bytes([1, 1, 0, 0])
        assert response.headers['X-Atlas-Dtype'] == 'uint8'
        assert response.headers['X-Atlas-Shape'] == '4'
        refused = client.post('/api/v1/datasets/toy/membership/projection', json={**query, 'snapshot_id': 'changed'}, headers={'X-Atlas-Request': '1'})
        assert refused.status_code == 422


def test_imported_embedding_browse_omits_both_vector_copies_but_full_stays_intact(root):
    with TestClient(create_app(root)) as client:
        response = client.get('/api/v1/artifacts?dataset_id=toy&view=browse')
        assert response.status_code == 200
        artifact = next(a for a in response.json() if a['id'] == 'imported')
        assert artifact['data']['items'][0]['output'] == {'label': 'kept'}
        assert set(artifact['data']['omitted_fields']) == {'vector', 'value'}
        full = client.get('/api/v1/artifacts/imported')
        assert full.status_code == 200
        assert full.json()['data']['items'][0]['output']['value'] == [1.0, 2.0]


def test_complete_field_descriptors_allow_more_than_32_historical_runs(root, monkeypatch):
    from dataset_atlas.registry import Registry
    from dataset_atlas.queries.parquet import build_parquet_snapshot
    p=root/'work/packs/toy/pack.json'
    pack=Pack.model_validate_json(p.read_text())
    pack.artifacts=[Artifact(id=f'result-{i}',kind='quality.basic',unit='example',snapshot_ids=['s1'],ids=[r.id for r in pack.records],
        data={'items':[{'id':r.id,'status':'completed','output':{'score':float(i)}} for r in pack.records]}) for i in range(40)]
    p.write_text(pack.model_dump_json())
    (root/'work/snapshots').mkdir()
    manifest=build_parquet_snapshot(pack.records,[],root/'work/snapshots/toy',root=root,
        dataset_id='toy',release_id='r1',snapshot_id='s1',expected_count=4,population_scope='complete')
    monkeypatch.setattr(Registry,'snapshot_path',lambda self,identity:manifest)
    with TestClient(create_app(root)) as client:
        response=client.get('/api/v1/datasets/toy/complete')
        assert response.status_code==200,response.text
        fields={f['id'] for f in response.json()['fields']}
        assert all(f'prediction.result-{i}.score' in fields for i in range(40))
        refused=client.post('/api/v1/queries/toy',headers={'X-Atlas-Request':'1'},json={
            'snapshot_id':'s1','population_scope':'complete','result_snapshot_ids':[a.id for a in pack.artifacts]})
        assert refused.status_code==422
