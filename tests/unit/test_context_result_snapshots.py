import json

import pytest
from fastapi.testclient import TestClient

from dataset_atlas.api import create_app
from dataset_atlas.models import Artifact, Pack
from dataset_atlas.providers.schemas import ContextRequest
from dataset_atlas.processors.analysis import compare
from dataset_atlas.queries.results import attach_results


def test_dotted_artifact_fields_are_exact_flat_keys_in_comparisons(pack):
    artifact = Artifact(id='artifact.fixture.v1', kind='import.research', snapshot_ids=['s1'], unit='example', ids=['r0', 'r1'],
                        data={'items': [{'id': 'r0', 'status': 'completed', 'output': {'value': 2}},
                                        {'id': 'r1', 'status': 'completed', 'output': {'value': 4}}]})
    joined = attach_results(pack, [artifact])
    result = compare(joined.records, {'left_field': 'source.score', 'right_field': 'prediction.artifact.fixture.v1.value', 'kind': 'correlation'})
    assert result['paired'] == 2 and result['pearson_r'] == pytest.approx(1)
    assert result['missing_right'] == 2


def test_api_context_joins_only_explicit_compatible_results_and_binds_digest(workspace):
    path = workspace / 'work/packs/fixture/pack.json'
    pack = Pack.model_validate_json(path.read_text())
    artifact = Artifact(id='artifact.fixture.v1', kind='import.research', snapshot_ids=['s1'], unit='example', ids=['r0'],
                        data={'items': [{'id': 'r0', 'status': 'completed', 'output': {'value': 42}}]})
    wrong = artifact.model_copy(update={'id': 'wrong', 'snapshot_ids': ['other']})
    wrong_unit = artifact.model_copy(update={'id': 'wrong-unit', 'unit': 'entity'})
    pack.artifacts = [artifact, wrong, wrong_unit]
    path.write_text(pack.model_dump_json())
    client = TestClient(create_app(workspace))
    headers = {'X-Atlas-Request': '1'}
    assert client.post('/api/v1/providers', headers=headers,
                      json={'id': 'local', 'base_url': 'http://127.0.0.1:1234/v1', 'model': 'fixture'}).status_code == 200
    request = {'provider_id': 'local', 'record_ids': ['r0'], 'snapshot_ids': ['s1'],
               'result_snapshot_ids': [artifact.id], 'fields': ['prediction.' + artifact.id + '.value']}
    response = client.post('/api/v1/conversations/context', headers=headers, json=request)
    assert response.status_code == 200, response.text
    preview = response.json()
    outgoing = json.loads(preview['outgoing'][0]['content'][0]['text'])
    assert outgoing['records'][0]['prediction.artifact.fixture.v1.value'] == 42
    assert preview['policy']['result_snapshot_ids'] == [artifact.id]
    no_results = {**request, 'result_snapshot_ids': [], 'fields': []}
    second = client.post('/api/v1/conversations/context', headers=headers, json=no_results).json()
    assert second['context_digest'] != preview['context_digest']
    for overrides in [{'result_snapshot_ids': ['wrong']}, {'result_snapshot_ids': ['wrong-unit']},
                      {'result_snapshot_ids': ['missing']}, {'snapshot_ids': ['other']}, {'mode': 'evaluation'}]:
        assert client.post('/api/v1/conversations/context', headers=headers, json={**request, **overrides}).status_code in {400, 422}
    client.close()


def test_context_result_approval_requires_unique_results_and_explicit_snapshot():
    with pytest.raises(ValueError, match='explicit dataset snapshot'):
        ContextRequest(provider_id='local', record_ids=['fixture'], result_snapshot_ids=['a'])
    with pytest.raises(ValueError, match='unique'):
        ContextRequest(provider_id='local', record_ids=['fixture'], snapshot_ids=['s1'], result_snapshot_ids=['a', 'a'])


def test_comparison_preserves_mixed_category_identity(pack):
    records = [pack.records[0].model_copy(update={'source': {'category': 1, 'other': True, 'value': 2}}),
               pack.records[1].model_copy(update={'source': {'category': '1', 'other': 'True', 'value': 6}})]
    cells = compare(records, {'left_field': 'source.category', 'right_field': 'source.other', 'kind': 'crosstab'})['cells']
    assert len(cells) == 2 and {row['left_type'] for row in cells} == {'int', 'str'}
    groups = compare(records, {'left_field': 'source.category', 'right_field': 'source.value', 'kind': 'grouped_numeric'})['groups']
    assert len(groups) == 2 and {row['mean'] for row in groups} == {2, 6}
