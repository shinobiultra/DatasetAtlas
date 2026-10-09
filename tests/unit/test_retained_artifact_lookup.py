import json
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest
from dataset_atlas.api import create_app
from dataset_atlas.models import Artifact
from dataset_atlas.registry import Registry
from dataset_atlas.registry.artifacts import RetainedArtifactIndex


def versions(workspace, pack):
    base=workspace/'work/prepared/fixture'
    old=pack.model_copy(deep=True)
    old.artifacts=[Artifact(id='old-result',kind='import.research',snapshot_ids=['s1'],unit='example',ids=['r0'],data={'items':[{'id':'r0','status':'completed','output':{'value':42}}]})]
    new=pack.model_copy(deep=True);new.dataset.snapshot_id='s2'
    for record in new.records:record.snapshot_id='s2'
    for name,value in [('old',old),('new',new)]:
        directory=base/name;(directory/'pack').mkdir(parents=True)
        (directory/'dataset.json').write_text(value.dataset.model_dump_json())
        (directory/'pack/pack.json').write_text(value.model_dump_json())
    (base/'active.json').write_text(json.dumps({'version':'new'}))
    return old,new


def test_retained_old_result_is_discoverable_and_context_uses_frozen_snapshot(workspace,pack):
    versions(workspace,pack)
    with TestClient(create_app(workspace)) as client:
        headers={'X-Atlas-Request':'1'}
        assert client.get('/api/v1/artifacts/old-result').status_code==200
        assert client.post('/api/v1/providers',headers=headers,json={'id':'local','base_url':'http://127.0.0.1:1234/v1','model':'fixture'}).status_code==200
        body={'provider_id':'local','record_ids':['r0'],'snapshot_ids':['s1'],'fields':['prediction.old-result.value'],'result_snapshot_ids':['old-result']}
        response=client.post('/api/v1/conversations/context',headers=headers,json=body)
        assert response.status_code==200,response.text
        outgoing=json.loads(response.json()['outgoing'][0]['content'][0]['text'])
        assert outgoing['records'][0]['prediction.old-result.value']==42


def test_read_only_tool_worker_resolves_old_result_only_in_approved_version(workspace,pack):
    versions(workspace,pack)
    payload={'root':str(workspace),'scope':['r0'],'record_versions':{'r0':{'dataset_id':'fixture','release_id':'r1','snapshot_id':'s1'}},
             'result_snapshot_ids':['old-result'],'jobs':False,'name':'aggregate','arguments':{'record_ids':['r0'],'field_id':'prediction.old-result.value'},'remaining_rows':5,'mode':'exploration'}
    result=subprocess.run([sys.executable,'-m','dataset_atlas.providers.tool_worker'],input=json.dumps(payload).encode(),capture_output=True,timeout=10,check=True)
    response=json.loads(result.stdout)
    assert 'error' not in response,response
    assert '42' in json.dumps(response)
    payload['record_versions']['r0']['snapshot_id']='s2'
    result=subprocess.run([sys.executable,'-m','dataset_atlas.providers.tool_worker'],input=json.dumps(payload).encode(),capture_output=True,timeout=10,check=True)
    assert 'error' in json.loads(result.stdout)


def test_duplicate_result_identity_requires_exact_immutable_contents(workspace,pack):
    old,new=versions(workspace,pack)
    new.artifacts=[old.artifacts[0].model_copy(update={'data':{'items':[]}})]
    (workspace/'work/prepared/fixture/new/pack/pack.json').write_text(new.model_dump_json())
    with pytest.raises(ValueError,match='conflicting immutable'):
        RetainedArtifactIndex(Registry(workspace)).list()


def test_oversized_retained_pack_is_refused_before_loading(workspace,pack,monkeypatch):
    from pathlib import Path
    versions(workspace,pack)
    path=workspace/'work/prepared/fixture/old/pack/pack.json'
    with path.open('r+b') as stream:stream.truncate(100_000_001)
    original=Path.read_bytes
    def read(candidate):
        assert candidate!=path,'Oversized pack must not be read'
        return original(candidate)
    monkeypatch.setattr(Path,'read_bytes',read)
    with pytest.raises(ValueError,match='interactive size budget'):
        RetainedArtifactIndex(Registry(workspace)).list()
