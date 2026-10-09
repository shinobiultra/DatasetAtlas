"""Browsing caches must never serve stale results or hide full artifacts (synthetic fixture only)."""
import sqlite3
from pathlib import Path

import pytest
import dataset_atlas
from fastapi.testclient import TestClient
from dataset_atlas.api import create_app
from dataset_atlas.models import Artifact

HEADERS={'X-Atlas-Request':'1'}
FRONTEND_BUILT = (Path(dataset_atlas.__file__).parent / 'web' / 'index.html').exists()
needs_frontend = pytest.mark.skipif(not FRONTEND_BUILT, reason='the interface is built into the package only by scripts/build_release.py')

def register(workspace, artifact):
    with sqlite3.connect(workspace/'work/jobs.sqlite3') as db:
        db.execute('INSERT OR IGNORE INTO artifacts(id,artifact_json) VALUES(?,?)',(artifact.id,artifact.model_dump_json()))

def embedding(id, snapshot):
    items=[{'id':'r0','status':'completed','output':{'vector':[0.1,0.2],'assets':[{'asset_id':'asset-1','vector':[0.3,0.4]}]}}]
    return Artifact(id=id,kind='embed.test',run_id='run-'+id,snapshot_ids=[snapshot],unit='example',ids=['r0'],data={'items':items,'points':items})

def test_browse_view_is_dataset_scoped_and_omits_only_vectors(workspace):
    with TestClient(create_app(workspace)) as client:
        register(workspace,embedding('mine','s1'))
        register(workspace,embedding('other','elsewhere'))
        browse=client.get('/api/v1/artifacts?view=browse&dataset_id=fixture').json()
        assert [a['id'] for a in browse]==['mine']
        assert "'vector':" not in str({k:v for k,v in browse[0]['data'].items() if k!='omitted_fields'})
        assert browse[0]['data']['omitted_fields']==['vector']
        assert browse[0]['data']['items'][0]['output']['assets'][0]['asset_id']=='asset-1'
        full=client.get('/api/v1/artifacts/mine').json()
        assert full['data']['items'][0]['output']['vector']==[0.1,0.2]
        assert {a['id'] for a in client.get('/api/v1/artifacts').json()}=={'mine','other'}
        assert client.get('/api/v1/artifacts?view=bogus').status_code==422

def test_cached_browser_pack_picks_up_newly_registered_runs(workspace):
    with TestClient(create_app(workspace)) as client:
        before=client.get('/api/v1/datasets/fixture/fields').json()
        assert not any(f['id'].startswith('prediction.') for f in before)
        query={'snapshot_id':'s1','unit':'example','population_scope':'preview','limit':10}
        assert client.post('/api/v1/queries/fixture',headers=HEADERS,json=query).json()['returned_count']==4
        detect=Artifact(id='det',kind='detect.test',run_id='run-det',snapshot_ids=['s1'],unit='example',ids=['r0'],data={'items':[{'id':'r0','status':'completed','output':{'detections':[]}}]})
        register(workspace,detect)
        after=client.get('/api/v1/datasets/fixture/fields').json()
        assert 'prediction.det.detection_count' in {f['id'] for f in after}
        filtered=client.post('/api/v1/queries/fixture',headers=HEADERS,json={**query,'result_snapshot_ids':['det'],'filter':{'field_id':'prediction.det.detection_count','op':'eq','value':0}}).json()
        assert [r['id'] for r in filtered['records']]==['r0']
        # A zero-detection result is attached only where computed; others stay missing, not zero.
        missing=client.post('/api/v1/queries/fixture',headers=HEADERS,json={**query,'result_snapshot_ids':['det'],'filter':{'field_id':'prediction.det.detection_count','op':'is_null','value':True}}).json()
        assert sorted(r['id'] for r in missing['records'])==['r1','r2','r3']
        # The unattached browsing query is unchanged by the cached attached variant.
        plain=client.post('/api/v1/queries/fixture',headers=HEADERS,json=query).json()
        assert all(not r['prediction'] for r in plain['records'])

def test_repeated_queries_from_cached_pack_serve_media(workspace):
    media=workspace/'work/packs/fixture/media'
    media.mkdir(parents=True)
    (media/'test.png').write_bytes(b'\x89PNG\r\n\x1a\n'+b'0'*32)
    app=create_app(workspace)
    with TestClient(app) as client:
        query={'snapshot_id':'s1','unit':'example','population_scope':'preview','limit':1}
        uri=client.post('/api/v1/queries/fixture',headers=HEADERS,json=query).json()['records'][0]['assets'][0]['uri']
        again=client.post('/api/v1/queries/fixture',headers=HEADERS,json=query).json()['records'][0]['assets'][0]['uri']
        assert again==uri and client.get(uri).status_code==200

@needs_frontend
def test_frontend_shell_revalidates(workspace):
    with TestClient(create_app(workspace)) as client:
        response=client.get('/')
        assert response.status_code==200 and response.headers['content-type'].startswith('text/html')
        assert response.headers['cache-control']=='no-cache'
        assert 'cache-control' not in client.get('/api/v1/capabilities').headers
