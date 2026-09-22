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
