import hashlib
import json
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from dataset_atlas.models import Dataset, Query
from dataset_atlas.adapters.columnar import ColumnarAdapter
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run
from dataset_atlas.registry import Registry
from dataset_atlas.queries.parquet import ParquetSnapshot


def fixture(root, count=117):
    data = root / 'source.parquet'
    pq.write_table(pa.table({'text': [f'record {i}' for i in range(count)], 'value': list(range(count))}), data)
    dataset = Dataset(id='real-fixture', name='Test fixture', release='pinned', snapshot_id='pinned-snapshot',
        adapter='columnar', adapter_config={'files': [{'path': str(data), 'sha256': hashlib.sha256(data.read_bytes()).hexdigest()}]},
        coverage={'total_count': count})
    directory = root / 'registry/datasets'; directory.mkdir(parents=True)
    (directory / 'fixture.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    return dataset


def test_full_preparation_and_runtime_registry(tmp_path):
    original = fixture(tmp_path)
    registry = Registry(tmp_path)
    assert registry.dataset(original.id).coverage.preview_count == 0
    manager = PreparationManager(tmp_path)
    plan = manager.plan(original.id, 1000000, 1000000)
    assert plan['ready'] and plan['expected_download_bytes'] == 0
    run(tmp_path, plan['id'])
    assert manager.status(plan['id'])['status'] == 'completed'
    dataset = registry.dataset(original.id)
    assert dataset.coverage.total_count == 117
    assert len(registry.pack(original.id).records) == 100
    snapshot = ParquetSnapshot(registry.snapshot_path(original.id).parent, registry.snapshot_path(original.id))
    result = snapshot.query(Query(snapshot_id=dataset.snapshot_id, population_scope='complete', limit=1000))
    assert result.matched_count == 117 and len(result.records) == 117
    assert max(r.source['value'] for r in result.records) == 116
    # Original manifest is never rewritten.
    assert yaml.safe_load((tmp_path/'registry/datasets/fixture.yaml').read_text())['coverage']['preview_count'] == 0


def test_shards_arrow_and_parquet_stable_ids(tmp_path):
    dataset = fixture(tmp_path, 3)
    arrow = tmp_path/'second.arrow'
    table = pa.table({'text': ['fourth', 'fifth'], 'value': [3, 4]})
    with pa.OSFile(str(arrow), 'wb') as sink:
        with pa.ipc.new_stream(sink, table.schema) as writer: writer.write_table(table)
    dataset.adapter_config['files'].append({'path': str(arrow), 'sha256': hashlib.sha256(arrow.read_bytes()).hexdigest()})
    adapter = ColumnarAdapter(dataset)
    source = adapter.prepare(adapter.plan(100, 1000000))
    records = adapter.iter_records(source).records
    assert len(records) == adapter.count == 5
    assert len({r.id for r in records}) == 5
    assert adapter.iter_records(source, '3', 2).records == records[3:]
    assert records[-1].source['_atlas_origin']['row'] == 1
    arrow.write_bytes(b'changed')
    with pytest.raises(ValueError, match='checksum'): adapter.prepare(adapter.plan(100, 1000000))


def test_budget_unknown_source_cancel_and_drift(tmp_path):
    dataset = fixture(tmp_path)
    manager = PreparationManager(tmp_path)
    with pytest.raises(ValueError): manager.plan(dataset.id, -1, 1000)
    with pytest.raises(ValueError): manager.status('../outside')
    plan = manager.plan(dataset.id, 1000000, 1000000)
    manager.cancel(plan['id'])
    run(tmp_path, plan['id'])
    assert manager.status(plan['id'])['status'] == 'cancelled'
    assert Registry(tmp_path).active_directory(dataset.id) is None
    path = tmp_path/'registry/datasets/fixture.yaml'
    raw = yaml.safe_load(path.read_text());raw['release'] = 'changed';path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match='changed after planning'): run(tmp_path, plan['id'])


def test_source_plan_pins_every_shard_and_no_download(monkeypatch, tmp_path):
    dataset = fixture(tmp_path)
    path=tmp_path/'registry/datasets/fixture.yaml'
    raw=yaml.safe_load(path.read_text());raw.update(adapter_config={}, source_url='https://huggingface.co/datasets/owner/repo');path.write_text(yaml.safe_dump(raw))
    monkeypatch.setattr('dataset_atlas.preparation.read_metadata', lambda url: {'sha':'a'*40,'gated':False,'siblings':[
        {'rfilename':'train/data.parquet','size':5000,'lfs':{'sha256':'b'*64}},
        {'rfilename':'README.md','size':10}]})
    manager=PreparationManager(tmp_path)
    plan=manager.plan(dataset.id,4000,1000)
    assert not plan['ready'] and plan['expected_download_bytes']==5000
    assert len(plan['files'])==1 and '/'+('a'*40)+'/' in plan['files'][0]['url']
    assert not (tmp_path/'work/download-cache').exists()
    with pytest.raises(ValueError,match='requirements'):manager.start(plan['id'])


def test_frozen_selection_resolves_previous_prepared_version(tmp_path):
    dataset=fixture(tmp_path)
    manager=PreparationManager(tmp_path);plan=manager.plan(dataset.id,1000000,1000000);run(tmp_path,plan['id'])
    registry=Registry(tmp_path);old=registry.pack(dataset.id).records[0]
    # Simulate a new immutable release activation while retaining the old version.
    active=registry.active_directory(dataset.id)
    import shutil
    new=active.parent/'new-version';shutil.copytree(active,new)
    doc=json.loads((new/'dataset.json').read_text());doc.update(release='new',snapshot_id='new')
    (new/'dataset.json').write_text(json.dumps(doc));(active.parent/'active.json').write_text(json.dumps({'version':'new-version'}))
    assert any(d.snapshot_id==old.snapshot_id for d,_,_ in registry.versions(dataset.id))
    assert registry.dataset_version(dataset.id,'pinned').snapshot_id==old.snapshot_id


def test_complete_scope_similarity(tmp_path):
    pytest.importorskip('lancedb')
    from fastapi.testclient import TestClient
    from dataset_atlas.api import create_app
    from dataset_atlas.models import Artifact
    dataset=fixture(tmp_path,1017)
    manager=PreparationManager(tmp_path);plan=manager.plan(dataset.id,10000000,10000000);run(tmp_path,plan['id'])
    registry=Registry(tmp_path);path=registry.snapshot_path(dataset.id)
    snap=ParquetSnapshot(path.parent,path)
    rows=[];cursor=None
    while True:
        result=snap.query(Query(snapshot_id=dataset.snapshot_id,population_scope='complete',limit=1000,cursor=cursor))
        rows.extend(result.records);cursor=result.cursor
        if not cursor:break
    artifact=Artifact(id='vectors',kind='embed.test',run_id='test-run',unit='example',snapshot_ids=[dataset.snapshot_id],
        ids=[r.id for r in rows],provenance={'processor_provenance':{'embedding_space_id':'test-space'}},
        data={'items':[{'id':r.id,'status':'completed','output':{'vector':[1,float(r.source['value'])/1017]}} for r in rows]})
    app=create_app(tmp_path)
    app.state.jobs.get_artifact=lambda _:artifact
    with TestClient(app) as client:
        response=client.post('/api/v1/similarity/'+dataset.id,headers={'X-Atlas-Request':'1'},json={
            'artifact_id':'vectors','record_id':rows[0].id,'query':{'snapshot_id':dataset.snapshot_id,'population_scope':'complete'},'limit':5})
    assert response.status_code==200,response.text
    assert response.json()['eligible_count']==1016
    assert len(response.json()['results'])==5
    assert response.json()['coverage']['filtered_records']==1017


def test_preview_output_budget_rejected_before_pack_write(tmp_path):
    dataset=fixture(tmp_path)
    from dataset_atlas.adapters import build_preview
    with pytest.raises(ValueError,match='output budget'):
        build_preview(dataset,tmp_path/'bounded-preview',max_bytes=1000000,max_output_bytes=1)
    assert not (tmp_path/'bounded-preview/pack.json').exists()


def test_columnar_schema_includes_late_fields_and_large_integers(tmp_path):
    import hashlib
    import pyarrow as pa
    import pyarrow.parquet as pq
    from dataset_atlas.adapters.columnar import ColumnarAdapter
    from dataset_atlas.models import Dataset
    files=[]
    for i,table in enumerate([pa.table({'early':['x'],'late':pa.nulls(1)}),pa.table({'early':['y'],'late':[{'label':'present'}],'identifier':[2**62]})]):
        path=tmp_path/f'{i}.parquet';pq.write_table(table,path)
        files.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'format':'parquet'})
    adapter=ColumnarAdapter(Dataset(id='schema',name='Schema',release='r',snapshot_id='s',adapter='columnar',adapter_config={'files':files}))
    assert adapter.source_field_types()=={'early':'string','late':'object','identifier':'object','_atlas_origin':'object'}
    source=adapter.prepare(adapter.plan(1,100000))
    assert adapter.iter_records(source,'1').records[0].source['identifier']==2**62


def test_source_recipe_restricts_release_split(monkeypatch,tmp_path):
    dataset=fixture(tmp_path)
    path=tmp_path/'registry/datasets/fixture.yaml'
    raw=yaml.safe_load(path.read_text());raw.update(adapter_config={},source_url='https://huggingface.co/datasets/owner/repo');path.write_text(yaml.safe_dump(raw))
    recipes=tmp_path/'registry/recipes';recipes.mkdir()
    (recipes/f'{dataset.id}.yaml').write_text(yaml.safe_dump({'source_patterns':['*/dev-*.parquet'],'expected_count':150,'scope':'Development split only'}))
    monkeypatch.setattr('dataset_atlas.preparation.read_metadata',lambda url:{'sha':'a'*40,'siblings':[
        {'rfilename':'subject/dev-0.parquet','size':100,'lfs':{'sha256':'b'*64}},
        {'rfilename':'subject/test-0.parquet','size':500,'lfs':{'sha256':'c'*64}}]})
    plan=PreparationManager(tmp_path).plan(dataset.id,1000,1000)
    assert plan['ready'] and plan['expected_count']==150 and plan['expected_download_bytes']==100
    assert plan['scope']=='Development split only' and len(plan['files'])==1
