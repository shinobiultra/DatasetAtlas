"""Synthetic same-release versions must preserve approved snapshot identity."""
import hashlib,io,json,time
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from dataset_atlas.adapters.core import MediaHandle
from dataset_atlas.api import create_app
from dataset_atlas.api.tools import make_tool_backend
from dataset_atlas.models import FieldDescriptor,Selection
from dataset_atlas.providers import ProviderService
from dataset_atlas.providers.schemas import ContextRequest,ProviderConfig
from dataset_atlas.registry import Registry


def prepared_versions(workspace,pack):
    versions={}
    for snapshot,color in [('old',(50,0,0)),('new',(0,50,0))]:
        stream=io.BytesIO();Image.new('RGB',(8,8),color).save(stream,'PNG');payload=stream.getvalue()
        version=pack.model_copy(deep=True);version.dataset.snapshot_id=snapshot
        version.dataset.adapter_config={'path':snapshot+'.jsonl'}
        version.records=[version.records[0]];record=version.records[0];record.snapshot_id=snapshot;record.text=snapshot+' fixture'
        record.assets[0].uri='file/fixture.png';record.assets[0].sha256=hashlib.sha256(payload).hexdigest()
        version.fields=[FieldDescriptor(id='source.'+snapshot,name=snapshot,dtype='string')]
        directory=workspace/'work/prepared/fixture'/snapshot;(directory/'pack').mkdir(parents=True)
        (directory/'dataset.json').write_text(version.dataset.model_dump_json());(directory/'pack/pack.json').write_text(version.model_dump_json())
        versions[snapshot]=(version,payload)
    (workspace/'work/prepared/fixture/active.json').write_text(json.dumps({'version':'new'}))
    return versions


@pytest.mark.parametrize('wrong_handle',[False,True])
def test_analysis_estimation_resolves_exact_frozen_snapshot_and_checks_original(workspace,pack,monkeypatch,wrong_handle):
    versions=prepared_versions(workspace,pack);seen=[]
    def resolve(dataset,ref,**kwargs):
        seen.append(dataset.snapshot_id);assert kwargs['allow_source_read'] is False
        payload=versions['new' if wrong_handle else dataset.snapshot_id][1]
        return MediaHandle(payload,'image/png',hashlib.sha256(payload).hexdigest(),ref)
    monkeypatch.setattr('dataset_atlas.adapters.resolve_dataset_asset',resolve)
    selection=Selection(id='frozen',ids=['r0'],dataset_ids=['fixture'],snapshot_ids=['old'],unit='example',created_at='now')
    with TestClient(create_app(workspace)) as client:
        assert client.post('/api/v1/selections',json=selection.model_dump(mode='json'),headers={'X-Atlas-Request':'1'}).status_code==200
        response=client.post('/api/v1/runs/estimate',json={'selection_id':'frozen','processor_id':'quality.basic','config':{}},headers={'X-Atlas-Request':'1'})
        assert response.status_code==(422 if wrong_handle else 200)
        if wrong_handle:assert 'selected asset checksum' in response.json()['detail']
    assert seen==['old']


def test_production_tool_reads_approved_old_records_and_field_metadata_after_activation(workspace,pack):
    prepared_versions(workspace,pack);registry=Registry(workspace)
    svc=ProviderService(workspace/'local-config/providers.json',lambda _:None,tool_backend=make_tool_backend(registry,lambda _:None,None))
    bindings={'r0':{'dataset_id':'fixture','release_id':'r1','snapshot_id':'old'}}
    for name in ['get_records','describe_dataset','describe_fields']:
        result=svc._execute_tool_bounded(name,{'record_ids':['r0'],'limit':1},frozenset({'r0'}),1,'exploration',time.monotonic()+10,bindings)['result']
        if name=='get_records':assert result['rows'][0]['snapshot_id']=='old' and result['rows'][0]['text']=='old fixture'
        elif name=='describe_dataset':assert result['data']['datasets'][0]['snapshot_id']=='old'
        else:assert [field['id'] for field in result['data']['fields']['fixture']]==['source.old']
    assert registry.dataset('fixture').snapshot_id=='new'


def test_frozen_record_lookup_fields_and_media_urls_do_not_rebind_after_activation(workspace,pack,monkeypatch):
    versions=prepared_versions(workspace,pack)
    def resolve(dataset,ref,**kwargs):
        payload=versions[dataset.snapshot_id][1]
        return MediaHandle(payload,'image/png',hashlib.sha256(payload).hexdigest(),ref)
    monkeypatch.setattr('dataset_atlas.adapters.resolve_dataset_asset',resolve)
    with TestClient(create_app(workspace)) as client:
        old=client.post('/api/v1/records',json={'ids':['r0'],'snapshot_ids':['old']},headers={'X-Atlas-Request':'1'}).json()[0]
        old_url=old['assets'][0]['uri'];assert client.get(old_url).content==versions['old'][1]
        new=client.post('/api/v1/records',json={'ids':['r0'],'snapshot_ids':['new']},headers={'X-Atlas-Request':'1'}).json()[0]
        assert old_url!=new['assets'][0]['uri'] and client.get(old_url).content==versions['old'][1]
        assert client.get(new['assets'][0]['uri']).content==versions['new'][1]
        assert client.get('/api/v1/datasets/fixture/fields?snapshot_id=old').json()[0]['id']=='source.old'
        assert client.post('/api/v1/records',json={'ids':['r0'],'snapshot_ids':['missing']},headers={'X-Atlas-Request':'1'}).status_code==404


def test_frozen_asset_fields_keep_the_old_snapshot_and_asset_unit(workspace,pack):
    versions=prepared_versions(workspace,pack)
    for snapshot,(version,_) in versions.items():
        version.records[0].assets[0].metadata={snapshot+'_width':8}
        (workspace/'work/prepared/fixture'/snapshot/'pack/pack.json').write_text(version.model_dump_json())
    with TestClient(create_app(workspace)) as client:
        old=client.get('/api/v1/datasets/fixture/fields?snapshot_id=old&unit=asset')
        assert old.status_code==200
        assert [(f['id'],f['unit']) for f in old.json()]==[('source.old_width','asset')]
        active=client.get('/api/v1/datasets/fixture/fields?unit=asset')
        assert active.status_code==200
        assert [(f['id'],f['unit']) for f in active.json()]==[('source.new_width','asset')]


def test_model_context_initial_lookup_uses_inspected_snapshot_and_refuses_missing_binding(workspace,pack):
    versions=prepared_versions(workspace,pack)
    service=ProviderService(workspace/'local-config/providers.json',lambda _:versions['new'][0].records[0],
        version_record_lookup=lambda identity,snapshots:next((value[0].records[0] for key,value in versions.items() if key in snapshots),None))
    service.put_provider(ProviderConfig(id='local',base_url='http://127.0.0.1:11434',model='fixture'))
    request=ContextRequest(provider_id='local',record_ids=['r0'],snapshot_ids=['old'])
    preview=service.preview(request)
    assert preview.policy['record_versions']['r0']['snapshot_id']=='old'
    assert 'old fixture' in preview.outgoing[0]['content'][0]['text']
    with pytest.raises(ValueError,match='unavailable'):service.preview(request.model_copy(update={'snapshot_ids':['missing']}))
    service.version_record_lookup=None
    with pytest.raises(ValueError,match='inspected snapshot'):service.preview(request)


def test_production_model_context_api_resolves_selected_old_snapshot(workspace,pack):
    prepared_versions(workspace,pack)
    headers={'X-Atlas-Request':'1'}
    with TestClient(create_app(workspace)) as client:
        assert client.post('/api/v1/providers',headers=headers,json={'id':'local','base_url':'http://127.0.0.1:11434','model':'fixture'}).status_code==200
        response=client.post('/api/v1/conversations/context',headers=headers,json={'provider_id':'local','record_ids':['r0'],'snapshot_ids':['old']})
        assert response.status_code==200
        assert response.json()['policy']['record_versions']['r0']['snapshot_id']=='old'
        assert client.post('/api/v1/conversations/context',headers=headers,json={'provider_id':'local','record_ids':['r0'],'snapshot_ids':['missing']}).status_code==400
