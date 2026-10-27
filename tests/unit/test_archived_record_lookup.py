"""Explicit frozen requests survive catalogue retirement without reviving cards."""
import hashlib
import io
import json
import subprocess
import sys

from fastapi.testclient import TestClient
from PIL import Image
import pytest
import yaml

from dataset_atlas.api import create_app
from dataset_atlas.models import Artifact, Record, Selection
from dataset_atlas.queries.parquet import build_parquet_snapshot
from dataset_atlas.registry import Registry
from dataset_atlas.registry.artifacts import RetainedArtifactIndex

HEADERS = {'X-Atlas-Request': '1'}


def archive(workspace, pack, *, count=3, preview=True, media=False, artifact=False):
    frozen = pack.model_copy(deep=True)
    rows = [Record(id=f'fixture:example:{i}', dataset_id='fixture', release_id='r1', snapshot_id='s1',
                   text=f'Frozen synthetic record {i}', source={'label': 'A', 'score': i}) for i in range(count)]
    frozen.records = rows[:2]
    directory = workspace / 'work/prepared/fixture/frozen'
    directory.mkdir(parents=True)
    payload = None
    if media:
        stream = io.BytesIO()
        Image.new('RGB', (4, 4), (20, 40, 60)).save(stream, 'PNG')
        payload = stream.getvalue()
        asset = pack.records[0].assets[0].model_copy(deep=True)
        asset.uri = 'media/one.png'
        asset.sha256 = hashlib.sha256(payload).hexdigest()
        rows[0].assets = [asset]
        rows[0].asset_ids = [asset.id]
        frozen.checksums = {'media/one.png': asset.sha256}
        target = directory / 'pack/media/one.png'
        target.parent.mkdir(parents=True)
        target.write_bytes(payload)
    if artifact:
        frozen.artifacts = [Artifact(id='frozen-result', kind='import.research', snapshot_ids=['s1'], unit='example',
                                     ids=[rows[0].id], data={'items':[{'id':rows[0].id, 'status':'completed', 'output':{'value':7}}]})]
    (directory / 'dataset.json').write_text(frozen.dataset.model_dump_json())
    build_parquet_snapshot(rows, frozen.fields, directory / 'snapshot', root=workspace,
                           dataset_id='fixture', release_id='r1', snapshot_id='s1',
                           expected_count=count, population_scope='complete')
    if preview:
        (directory / 'pack').mkdir(exist_ok=True)
        (directory / 'pack/pack.json').write_text(frozen.model_dump_json())
    (workspace / 'registry/datasets/fixture.yaml').unlink()
    (workspace / 'work/packs/fixture/pack.json').unlink()
    return rows, payload


@pytest.mark.parametrize('preview', [True, False])
def test_explicit_retired_records_and_complete_fields_work_without_a_card_or_preview(workspace, pack, preview):
    rows, _ = archive(workspace, pack, preview=preview)
    with TestClient(create_app(workspace)) as client:
        assert client.get('/api/v1/datasets').json() == []
        request = {'ids':[rows[-1].id, rows[0].id], 'snapshot_ids':['s1']}
        response = client.post('/api/v1/records', headers=HEADERS, json=request)
        assert response.status_code == 200, response.text
        assert [row['text'] for row in response.json()] == [rows[-1].text, rows[0].text]
        fields = client.get('/api/v1/datasets/fixture/fields?snapshot_id=s1&population_scope=complete')
        assert fields.status_code == 200, fields.text
        assert 'source.score' in {field['id'] for field in fields.json()}
        assert client.post('/api/v1/records', headers=HEADERS, json={'ids':[rows[0].id]}).status_code == 404
        assert client.get('/api/v1/datasets').json() == []


def test_large_frozen_selection_reads_complete_snapshot_without_a_preview(workspace, pack):
    rows, _ = archive(workspace, pack, count=501, preview=False)
    selection = Selection(id='frozen', ids=[row.id for row in reversed(rows)], dataset_ids=['fixture'],
                          snapshot_ids=['s1'], unit='example', created_at='now')
    with TestClient(create_app(workspace)) as client:
        resolved = client.app.state.selection_records(selection, prepare_media=False)
        assert [row.id for row in resolved] == selection.ids
        assert resolved[0].text == 'Frozen synthetic record 500'


def test_retired_preview_original_remains_readable_by_its_frozen_media_token(workspace, pack):
    rows, payload = archive(workspace, pack, media=True)
    with TestClient(create_app(workspace)) as client:
        response = client.post('/api/v1/records', headers=HEADERS,
                               json={'ids':[rows[0].id], 'snapshot_ids':['s1']})
        assert response.status_code == 200, response.text
        uri = response.json()[0]['assets'][0]['uri']
        media = client.get(uri)
        assert media.status_code == 200, media.text
        assert media.content == payload


@pytest.mark.parametrize('name', ['get_records', 'describe_dataset', 'describe_fields'])
def test_disposable_tools_use_approved_retired_complete_snapshot_without_preview(workspace, pack, name):
    rows, _ = archive(workspace, pack, preview=False)
    identity = rows[-1].id
    payload = {'root':str(workspace), 'scope':[identity],
               'record_versions':{identity:{'dataset_id':'fixture', 'release_id':'r1', 'snapshot_id':'s1'}},
               'result_snapshot_ids':[], 'jobs':False, 'name':name, 'arguments':{'record_ids':[identity], 'limit':1},
               'remaining_rows':1, 'mode':'exploration'}
    process = subprocess.run([sys.executable, '-m', 'dataset_atlas.providers.tool_worker'],
                             input=json.dumps(payload).encode(), capture_output=True, timeout=10, check=True)
    response = json.loads(process.stdout)
    assert 'error' not in response, response
    result = response['receipt']['result']
    assert result['source_refs'] == [identity]
    if name == 'get_records':assert result['rows'][0]['text'] == rows[-1].text
    if name == 'describe_dataset':assert result['data']['datasets'][0]['id'] == 'fixture'
    if name == 'describe_fields':assert 'source.score' in {f['id'] for f in result['data']['fields']['fixture']}


def test_retained_artifacts_need_explicit_snapshot_to_find_a_retired_card(workspace, pack):
    archive(workspace, pack, artifact=True)
    index = RetainedArtifactIndex(Registry(workspace))
    assert index.list() == []
    assert [artifact.id for artifact in index.list({'s1'})] == ['frozen-result']
    assert [artifact.id for artifact in index.list({'s1'}, {'fixture'})] == ['frozen-result']


def test_explicit_retired_lookup_never_rebinds_to_a_current_alias(workspace, pack):
    rows, _ = archive(workspace, pack)
    current = pack.model_copy(deep=True)
    current.dataset.id = 'current'
    current.dataset.aliases = ['fixture']
    current.records = [rows[0].model_copy(update={'dataset_id':'current', 'text':'Current different content'})]
    (workspace / 'registry/datasets/current.yaml').write_text(yaml.safe_dump(current.dataset.model_dump()))
    directory = workspace / 'work/packs/current'
    directory.mkdir()
    (directory / 'pack.json').write_text(current.model_dump_json())
    with TestClient(create_app(workspace)) as client:
        response = client.post('/api/v1/records', headers=HEADERS,
                               json={'ids':[rows[0].id], 'snapshot_ids':['s1']})
        assert response.status_code == 200, response.text
        assert response.json()[0]['dataset_id'] == 'fixture'
        assert response.json()[0]['text'] == rows[0].text
        assert [d['id'] for d in client.get('/api/v1/datasets').json()] == ['current']


def test_frozen_model_context_can_attach_retired_result_without_default_listing(workspace, pack):
    rows, _ = archive(workspace, pack, artifact=True)
    with TestClient(create_app(workspace)) as client:
        assert client.post('/api/v1/providers', headers=HEADERS,
                           json={'id':'local', 'base_url':'http://127.0.0.1:1234/v1', 'model':'fixture'}).status_code == 200
        response = client.post('/api/v1/conversations/context', headers=HEADERS,
                               json={'provider_id':'local', 'record_ids':[rows[0].id], 'snapshot_ids':['s1'],
                                     'fields':['prediction.frozen-result.value'], 'result_snapshot_ids':['frozen-result']})
        assert response.status_code == 200, response.text
        outgoing = json.loads(response.json()['outgoing'][0]['content'][0]['text'])
        assert outgoing['records'][0]['prediction.frozen-result.value'] == 7
        assert client.get('/api/v1/artifacts').json() == []


def test_current_native_media_route_uses_exact_baseline_source_config_with_sanitized_pack(workspace, pack):
    directory = workspace / 'work/native'
    directory.mkdir()
    source = directory / 'records.json'
    source.write_text('[]')
    image = directory / 'source.png'
    Image.new('RGB', (4, 4), (10, 30, 50)).save(image, 'PNG')
    payload = image.read_bytes()
    pack.records[0].assets[0].uri = 'source.png'
    pack.records[0].assets[0].sha256 = hashlib.sha256(payload).hexdigest()
    # The preview is sanitized; source routing lives only in current registry metadata.
    assert pack.dataset.adapter_config == {}
    (workspace / 'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    current = pack.dataset.model_copy(update={'adapter':'structured', 'adapter_config':{
        'path':'work/native/records.json', 'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'media_root':'work/native'}})
    (workspace / 'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(current.model_dump()))
    with TestClient(create_app(workspace)) as client:
        response = client.post('/api/v1/records', headers=HEADERS, json={'ids':['r0'], 'snapshot_ids':['s1']})
        assert response.status_code == 200, response.text
        media = client.get(response.json()[0]['assets'][0]['uri'])
        assert media.status_code == 200, media.text
        assert media.content == payload
