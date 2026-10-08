from fastapi.testclient import TestClient
from dataset_atlas.api import create_app

HEADERS={'X-Atlas-Request':'1'}
def test_workbench_queries_selection_and_security(workspace):
    with TestClient(create_app(workspace)) as client:
        assert client.get('/api/v1/capabilities').json()['mode']=='workbench'
        assert len(client.get('/api/v1/datasets').json())==1
        assert client.post('/api/v1/queries/fixture',json={'snapshot_id':'s1'}).status_code==403
        reply=client.post('/api/v1/queries/fixture',json={'snapshot_id':'s1'},headers=HEADERS)
        assert reply.status_code==200 and reply.json()['matched_count']==4
        assert reply.json()['records'][0]['assets'][0]['uri'].startswith('/api/v1/media/')
        saved=client.post('/api/v1/selections',headers=HEADERS,json={'id':'','name':'test','ids':['r0','r1'],'unit':'example','snapshot_ids':['s1'],'dataset_ids':['fixture'],'created_at':'2026-09-22T00:00:00Z'})
        assert saved.status_code==200
        identity=saved.json()['id']
        assert client.get(f'/api/v1/selections/{identity}').json()['ids']==['r0','r1']
        exchange=client.get(f'/api/v1/selections/{identity}/export').json()
        assert exchange['records'][0]['assets'][0]['uri'] is None
        assert client.post('/api/v1/selections/import',json=exchange,headers=HEADERS).status_code==200
        exchange['records'][0]['source']['label']='tampered'
        rejected=client.post('/api/v1/selections/import',json=exchange,headers=HEADERS)
        assert rejected.status_code==422 and 'checksum' in rejected.json()['detail']
        altered=saved.json();altered['name']='changed'
        assert client.post('/api/v1/selections',json=altered,headers=HEADERS).status_code==422
        assert client.get('/api/v1/datasets',headers={'Host':'evil.test'}).status_code==403
        assert client.get('/api/v1/datasets',headers={'Origin':'https://evil.test'}).status_code==403
        assert client.post('/api/v1/queries/fixture',headers=HEADERS,json={'snapshot_id':'unknown'}).status_code==422

def test_selection_does_not_accept_wrong_snapshot(workspace):
    with TestClient(create_app(workspace)) as client:
        reply=client.post('/api/v1/selections',headers=HEADERS,json={'id':'bad','ids':['r0'],'unit':'asset','snapshot_ids':['s1'],'dataset_ids':['fixture'],'created_at':'now'})
        assert reply.status_code==422

def test_media_ranges_head_and_cache_validation(workspace):
    media=workspace/'work/packs/fixture/media'
    media.mkdir()
    (media/'test.png').write_bytes(b'0123456789')
    with TestClient(create_app(workspace)) as client:
        pack=client.get('/api/v1/datasets/fixture/pack').json()
        uri=pack['records'][0]['assets'][0]['uri']
        whole=client.get(uri)
        assert whole.status_code==200 and whole.content==b'0123456789'
        part=client.get(uri,headers={'Range':'bytes=2-5'})
        assert part.status_code==206 and part.content==b'2345'
        assert part.headers['content-range']=='bytes 2-5/10'
        assert client.get(uri,headers={'Range':'bytes=-3'}).content==b'789'
        head=client.head(uri,headers={'Range':'bytes=5-'})
        assert head.status_code==206 and head.content==b'' and head.headers['content-length']=='5'
        assert client.get(uri,headers={'Range':'bytes=11-'}).status_code==416
        assert client.get(uri,headers={'Range':'bytes=0-1,3-4'}).status_code==416
        assert client.get(uri,headers={'Range':'bytes='+('9'*5000)+'-'}).status_code==416
        assert client.get(uri,headers={'Range':'bytes=-0'}).status_code==416
        assert client.get(uri,headers={'If-None-Match':whole.headers['etag']}).status_code==304
        assert client.get(uri,headers={'Range':'bytes=2-5','If-Range':'"other"'}).content==whole.content


def test_prepared_preview_originals_are_local_and_checksum_verified(workspace, pack, monkeypatch, tmp_path):
    import hashlib
    import io
    import json
    from PIL import Image
    from dataset_atlas import adapters
    buffer = io.BytesIO()
    Image.new('RGB', (3, 2), 'blue').save(buffer, format='PNG')
    data = buffer.getvalue()
    sha = hashlib.sha256(data).hexdigest()
    uri = 'media/' + sha
    version = workspace/'work/prepared/fixture/local-version'
    (version/'pack/media').mkdir(parents=True)
    native = version/'pack'/uri
    native.write_bytes(data)
    local = pack.model_copy(deep=True)
    for record in local.records:
        record.assets[0].uri = uri
        record.assets[0].sha256 = sha
        record.assets[0].metadata['source_ref'] = 'remote/0/0/image/0.png'
    local.checksums = {uri: sha}
    (version/'pack/pack.json').write_text(local.model_dump_json())
    (version/'dataset.json').write_text(local.dataset.model_dump_json())
    (version.parent/'active.json').write_text(json.dumps({'version': version.name}))

    def no_remote(*args, **kwargs):
        raise AssertionError('Prepared original must not read its remote source')
    monkeypatch.setattr(adapters, 'resolve_dataset_asset', no_remote)
    app = create_app(workspace)
    with TestClient(app) as client:
        response = client.get('/api/v1/datasets/fixture/pack')
        assert response.status_code == 200
        route = response.json()['records'][0]['assets'][0]['uri']
        response = client.get(route)
        assert response.status_code == 200 and response.content == data
        assert response.headers['content-type'] == 'image/png'
        assert client.get(route, headers={'Range': 'bytes=0-7'}).content == data[:8]
        from dataset_atlas.models import Selection
        selection = Selection(id='local-original-test', ids=['r0'], dataset_ids=['fixture'], snapshot_ids=['s1'], unit='example', created_at='2026-10-05T00:00:00Z')
        prepared = app.state.selection_records(selection)
        assert prepared[0].assets[0].uri == str(native)
        assert native.read_bytes() == data
        native.write_bytes(data + b'changed')
        assert client.get(route).status_code == 422
        native.unlink()
        outside = tmp_path/'outside-original.png'
        outside.write_bytes(data)
        native.symlink_to(outside)
        assert client.get(route).status_code == 422
    # A caller's explicit root policy still controls managed prepared files.
    native.unlink();native.write_bytes(data)
    with TestClient(create_app(workspace, allowed_roots=[workspace/'work/packs'])) as client:
        route = client.get('/api/v1/datasets/fixture/pack').json()['records'][0]['assets'][0]['uri']
        assert client.get(route).status_code == 422


def test_run_estimation_and_unapproved_start_never_acquire_originals(workspace, monkeypatch):
    from dataset_atlas import adapters
    calls=[]
    def unavailable(dataset,ref,**kwargs):
        calls.append(kwargs)
        assert kwargs['allow_source_read'] is False
        raise FileNotFoundError('Not retained')
    monkeypatch.setattr(adapters,'resolve_dataset_asset',unavailable)
    import yaml
    baseline=workspace/'registry/datasets/fixture.yaml'
    value=yaml.safe_load(baseline.read_text());value['adapter_config']={'max_record_bytes':1000}
    baseline.write_text(yaml.safe_dump(value))
    with TestClient(create_app(workspace)) as client:
        selection=client.post('/api/v1/selections',headers=HEADERS,json={'id':'','ids':['r0'],'unit':'example',
          'snapshot_ids':['s1'],'dataset_ids':['fixture'],'created_at':'now'}).json()
        body={'selection_id':selection['id'],'processor_id':'quality.basic','config':{}}
        response=client.post('/api/v1/runs/estimate',headers=HEADERS,json=body)
        assert response.status_code == 422 and 'estimation does not acquire' in response.json()['detail']
        response=client.post('/api/v1/runs',headers=HEADERS,json=body)
        assert response.status_code == 422
        assert len(calls)==2 and all(call['allow_source_read'] is False for call in calls)
        # Text and derived-result processors do not need image materialization.
        response=client.post('/api/v1/runs/estimate',headers=HEADERS,json={**body,'processor_id':'compare.fields'})
        assert response.status_code==200 and response.json()['expected_download_bytes']==0
        assert len(calls)==2
        for representation in ('text','question'):
            response=client.post('/api/v1/runs/estimate',headers=HEADERS,json={**body,'processor_id':'embed.siglip2','config':{'representation':representation}})
            assert response.status_code==200 and response.json()['expected_download_bytes']==0
            assert len(calls)==2


def test_provider_context_materializes_only_explicit_images_from_local_sources(workspace,pack,monkeypatch):
    import json,yaml
    from PIL import Image
    from dataset_atlas import adapters
    from dataset_atlas.models import Asset
    from dataset_atlas.providers import ProviderService
    from dataset_atlas.providers.schemas import ProviderConfig
    calls=[]
    def unavailable(dataset,ref,**kwargs):
        calls.append(ref)
        assert kwargs['allow_source_read'] is False
        raise FileNotFoundError('Original not retained')
    monkeypatch.setattr(adapters,'resolve_dataset_asset',unavailable)
    baseline=workspace/'registry/datasets/fixture.yaml'
    value=yaml.safe_load(baseline.read_text());value['adapter_config']={'max_record_bytes':1000}
    baseline.write_text(yaml.safe_dump(value))
    pack.records[0].assets.append(Asset(id='unselected',dataset_id='fixture',release_id=pack.dataset.release,modality='image',uri='missing.png'))
    (workspace/'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    media=workspace/'work/packs/fixture/media';media.mkdir();Image.new('RGB',(2,2),'red').save(media/'test.png')
    config=workspace/'local-config/providers.json'
    provider=ProviderService(config,lambda _:None)
    view=provider.put_provider(ProviderConfig(id='local',base_url='http://127.0.0.1:1234/v1',model='synthetic'))
    view.capabilities['single_image_input'].status='supported'
    config.write_text(json.dumps([view.model_dump(mode='json')]))
    with TestClient(create_app(workspace)) as client:
        body={'provider_id':'local','record_ids':['r0']}
        response=client.post('/api/v1/conversations/context',headers=HEADERS,json=body)
        assert response.status_code==200 and calls==[]
        response=client.post('/api/v1/conversations/context',headers=HEADERS,json={**body,'image_asset_ids':[pack.records[0].assets[0].id]})
        assert response.status_code==200 and len(response.json()['image_representations'])==1 and calls==[]
        response=client.post('/api/v1/conversations/context',headers=HEADERS,json={**body,'image_asset_ids':['unselected']})
        assert response.status_code in (409,422) and calls==['missing.png']
