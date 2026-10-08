import copy

import pytest
from fastapi.testclient import TestClient

from dataset_atlas.api import create_app
from dataset_atlas.models import Artifact, Pack
from dataset_atlas.processors import run_processor
from dataset_atlas.queries.embedding_space import embedding_vectors, is_embedding_artifact
from dataset_atlas.queries.similarity import similar_records


def imported(pack, metric='euclidean'):
    config = {'rows': [{'id': 'r0', 'value': [1, 0]}, {'id': 'r1', 'value': [2, 0]}, {'id': 'r2', 'value': [0, 4]}],
              'field_id': 'prediction.fixture_vector', 'kind': 'vector', 'dimension': 2,
              'rights': 'private', 'source_reference': 'synthetic:test',
              'embedding_space': {'model_revision': 'synthetic-v1', 'representation': 'fixture numeric values', 'metric': metric, 'normalized': False}}
    result = run_processor('import.research', pack.records, config)
    return Artifact(id='import.fixture', kind='import.research', unit='example', snapshot_ids=['s1'], ids=[r.id for r in pack.records],
                    provenance={'processor_provenance': result['provenance']}, data={'items': result['items']}), config


def test_registered_import_pca_and_exact_retrieval_preserve_original_vectors(pack, tmp_path):
    artifact, config = imported(pack)
    before = copy.deepcopy(artifact.model_dump())
    vectors, provenance, metric = embedding_vectors(artifact)
    projection = run_processor('project.pca', pack.records, {'vectors': vectors, 'embedding_space_id': provenance['embedding_space_id'],
                               'embedding_run_id': artifact.id, 'embedding_snapshot_ids': ['s1'], 'embedding_unit': 'example'})
    assert projection['coverage']['statuses'] == {'completed': 3, 'not_applicable': 1}
    pytest.importorskip('lancedb')
    found = similar_records(artifact, 'r0', ['r1', 'r2'], 2, tmp_path / 'vectors')
    assert [row['id'] for row in found['results']] == ['r1', 'r2']
    assert found['metric'] == metric == 'euclidean'
    assert artifact.model_dump() == before
    config.pop('embedding_space')
    raw = run_processor('import.research', pack.records, config)
    raw_artifact = artifact.model_copy(update={'provenance': {'processor_provenance': raw['provenance']}, 'data': {'items': raw['items']}})
    assert not is_embedding_artifact(raw_artifact)
    with pytest.raises(ValueError, match='explicitly registered'):
        embedding_vectors(raw_artifact)


def test_import_registration_rejects_false_norm_or_ambiguous_space(pack):
    _, config = imported(pack)
    config['embedding_space']['normalized'] = True
    with pytest.raises(ValueError, match='normalization'):
        run_processor('import.research', pack.records, config)
    config['embedding_space'].pop('model_revision')
    with pytest.raises(ValueError, match='model_revision'):
        run_processor('import.research', pack.records, config)


@pytest.mark.parametrize('change', ['dimension', 'model_revision', 'normalized', 'subject'])
def test_registered_space_is_revalidated_when_loaded(pack, change):
    artifact, _ = imported(pack)
    if change == 'subject':
        artifact.data['items'][0]['id'] = 'outside'
    else:
        artifact.provenance['processor_provenance']['embedding_space'][change] = {'dimension': 3, 'model_revision': 'changed', 'normalized': True}[change]
    with pytest.raises(ValueError):
        embedding_vectors(artifact)


@pytest.mark.parametrize('unit', ['example', 'asset', 'entity', 'conversation'])
def test_projection_accepts_explicit_registered_units(pack, unit):
    records = [record.model_copy(update={'unit': unit}) for record in pack.records]
    artifact, _ = imported(pack.model_copy(update={'records': records}))
    artifact.unit = unit
    vectors, provenance, _ = embedding_vectors(artifact)
    result = run_processor('project.pca', records, {'vectors': vectors, 'embedding_space_id': provenance['embedding_space_id'], 'embedding_run_id': artifact.id,
                           'embedding_snapshot_ids': ['s1'], 'embedding_unit': unit})
    assert result['provenance']['sample_unit'] == unit


def test_registered_vectors_reject_float32_overflow_while_raw_import_preserves_it(pack):
    _, config = imported(pack)
    config['rows'][0]['value'] = [1e40, 1]
    with pytest.raises(ValueError, match='float32'):
        run_processor('import.research', pack.records, config)
    config.pop('embedding_space')
    result = run_processor('import.research', pack.records, config)
    assert result['items'][0]['output']['value'] == [1e40, 1]


def test_api_projection_accepts_registered_pack_import_and_rejects_wrong_snapshot(workspace):
    path = workspace / 'work/packs/fixture/pack.json'
    pack = Pack.model_validate_json(path.read_text())
    artifact, _ = imported(pack)
    pack.artifacts = [artifact]
    path.write_text(pack.model_dump_json())
    client = TestClient(create_app(workspace))
    config = client.app.state.run_config('project.pca', {'embedding_artifact_id': artifact.id})
    assert config['embedding_run_id'] == artifact.id
    result = run_processor('project.pca', pack.records, config)
    assert result['coverage']['statuses']['completed'] == 3
    wrong = pack.records[0].model_copy(update={'snapshot_id': 'wrong'})
    with pytest.raises(ValueError, match='snapshot'):
        run_processor('project.pca', [wrong, pack.records[1]], config)
    client.close()
