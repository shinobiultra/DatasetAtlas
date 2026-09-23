import hashlib
import json
import os
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
    pq.write_table(pa.table({'text': [f'record {i}' for i in range(count)], 'value': pa.array(range(count),type=pa.int32())}), data)
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
    preview = registry.pack(original.id)
    assert preview.sampling['method'] == 'sha256_bottom_k_primary_asset'
    assert preview.sampling['population_count'] == 117
    assert max(r.source['value'] for r in preview.records) > 100
    snapshot = ParquetSnapshot(registry.snapshot_path(original.id).parent, registry.snapshot_path(original.id))
    result = snapshot.query(Query(snapshot_id=dataset.snapshot_id, population_scope='complete', limit=1000))
    assert result.matched_count == 117 and len(result.records) == 117
    assert max(r.source['value'] for r in result.records) == 116
    filtered=snapshot.query(Query(snapshot_id=dataset.snapshot_id,population_scope='complete',filter={'field_id':'source.value','op':'gt','value':115}))
    assert filtered.matched_count==1 and filtered.records[0].source['value']==116
    # Original manifest is never rewritten.
    assert yaml.safe_load((tmp_path/'registry/datasets/fixture.yaml').read_text())['coverage']['preview_count'] == 0


def test_shared_storage_rechecks_headroom_before_dispatch(tmp_path):
    from dataset_atlas.storage.optimized import configure_storage
    dataset = fixture(tmp_path, 3)
    configure_storage(tmp_path, target_bytes=2_000_000, ceiling_bytes=3_000_000, optimized_cache_bytes=100_000)
    manager = PreparationManager(tmp_path)
    plan = manager.plan(dataset.id, 100_000, 1_000_000)
    assert plan['ready'] and plan['shared_storage']['admitted']
    (tmp_path/'new-retained-source').write_bytes(b'x' * 2_500_000)
    with pytest.raises(ValueError, match='headroom changed'): manager.start(plan['id'])
    blocked = manager.plan(dataset.id, 100_000, 1_000_000)
    assert not blocked['ready'] and not blocked['shared_storage']['admitted']


@pytest.mark.parametrize('selected_count', [1, 2])
def test_filtered_index_counts_actual_image_population_and_samples_it(tmp_path, selected_count):
    import io
    from PIL import Image
    dataset=fixture(tmp_path,3)
    image=io.BytesIO();Image.new('RGB',(2,2),'blue').save(image,'PNG')
    path=tmp_path/'source.parquet'
    pq.write_table(pa.Table.from_pylist([{'text':'plain','image':None},
        {'text':'with image','image':{'bytes':image.getvalue(),'path':'image.png'}},
        {'text':'plain again','image':None}]),path)
    dataset.adapter_config['files'][0]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    dataset.adapter_config.update(record_filter={'asset_modality':'image'},expected_source_count=3)
    dataset.coverage.total_count=selected_count
    (tmp_path/'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    manager=PreparationManager(tmp_path);plan=manager.plan(dataset.id,1_000_000,1_000_000)
    if selected_count==2:
        with pytest.raises(ValueError):run(tmp_path,plan['id'])
        assert Registry(tmp_path).active_directory(dataset.id) is None
    else:
        run(tmp_path,plan['id'])
        pack=Registry(tmp_path).pack(dataset.id)
        assert len(pack.records)==1 and len(pack.records[0].assets)==1
        assert pack.records[0].text=='with image'
        assert pack.sampling['population_count']==1


def test_storage_reservations_include_jobs_older_than_ui_listing(tmp_path, monkeypatch):
    fixture(tmp_path, 1)
    manager = PreparationManager(tmp_path)
    for i in range(101):
        directory = manager._path(f'{i:064x}'); directory.mkdir()
        (directory/'status.json').write_text('{}')
        (directory/'plan.json').write_text(json.dumps({'required_free_bytes': 10}))
    monkeypatch.setattr(manager, 'status', lambda identity: {'id': identity, 'status':'running'})
    assert manager._storage_reservations() == 1010


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


def test_refresh_metadata_is_idempotent_and_prune_removes_only_unreachable_versions(tmp_path):
    import shutil
    dataset = fixture(tmp_path)
    manager = PreparationManager(tmp_path)
    plan = manager.plan(dataset.id, 1_000_000, 1_000_000)
    run(tmp_path, plan['id'])
    registry = Registry(tmp_path)
    active = registry.active_directory(dataset.id)
    # Reproduce the out-of-tree edit: a hard-linked twin with rewritten metadata, made active.
    twin = active.parent / (active.name + '-metadata-v2')
    shutil.copytree(active, twin, copy_function=os.link)
    (active.parent / 'active.json').write_text(json.dumps({'version': twin.name}))
    # A failed run leaves its directory behind too.
    failed = active.parent / ('deadbeef' * 8)
    failed.mkdir()
    (failed / 'dataset.json').write_text(json.dumps({**json.loads((active / 'dataset.json').read_text()), 'snapshot_id': 'never-activated'}))
    (failed / 'junk.bin').write_bytes(b'x' * 4096)
    (manager.directory / failed.name).mkdir()
    (manager.directory / failed.name / 'status.json').write_text(json.dumps({'status': 'failed'}))

    first = manager.refresh_metadata(dataset.id, active.name, activate=True)
    second = manager.refresh_metadata(dataset.id, active.name)
    assert first['active'] and second['active'] and first['snapshot_id'] == second['snapshot_id']
    document = json.loads((active / 'dataset.json').read_text())
    assert sum(item.get('kind') == 'local_preparation' for item in document['evidence']) == 1
    assert json.loads((active / 'receipt.json').read_text())['metadata_version'] == 2
    assert json.loads((active / 'pack/pack.json').read_text())['dataset']['adapter_config'] == {}
    assert registry.active_directory(dataset.id) == active

    preview = manager.prune()
    reasons = {entry['version']: entry['reason'] for entry in preview['removable']}
    assert reasons[twin.name] == 'duplicate of active snapshot'
    assert reasons[failed.name] == 'failed'
    assert all(entry['version'] != active.name for entry in preview['removable'])
    # The twin shares every source/snapshot inode with the retained version, so it frees only the
    # documents the refresh rewrote (now unique to it); the failed run frees its whole payload.
    twin_entry = next(entry for entry in preview['removable'] if entry['version'] == twin.name)
    failed_entry = next(entry for entry in preview['removable'] if entry['version'] == failed.name)
    assert 0 < twin_entry['freed_bytes'] < 1_000_000 and failed_entry['freed_bytes'] >= 4096
    assert twin.exists() and failed.exists()

    result = manager.prune(execute=True)
    assert result['executed'] and not twin.exists() and not failed.exists() and active.exists()
    assert registry.dataset(dataset.id).snapshot_id == first['snapshot_id']


def test_prune_keeps_superseded_versions_a_saved_selection_still_references(tmp_path):
    import shutil, sqlite3
    dataset = fixture(tmp_path)
    manager = PreparationManager(tmp_path)
    plan = manager.plan(dataset.id, 1_000_000, 1_000_000)
    run(tmp_path, plan['id'])
    registry = Registry(tmp_path)
    old = registry.active_directory(dataset.id)
    new = old.parent / 'newer-version'
    shutil.copytree(old, new)
    document = json.loads((new / 'dataset.json').read_text()); document.update(release='new', snapshot_id='new-snapshot')
    (new / 'dataset.json').write_text(json.dumps(document))
    (old.parent / 'active.json').write_text(json.dumps({'version': new.name}))
    db = sqlite3.connect(tmp_path / 'work/atlas.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS selections (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    old_snapshot = json.loads((old / 'dataset.json').read_text())['snapshot_id']
    db.execute('INSERT INTO selections VALUES (?,?)', ('s1', json.dumps({'id': 's1', 'ids': ['x'], 'unit': 'example', 'snapshot_ids': [old_snapshot], 'dataset_ids': [dataset.id], 'created_at': 'now'})))
    db.commit(); db.close()
    report = manager.prune()
    retained = {entry['version']: entry['reason'] for entry in report['retained']}
    assert retained[old.name] == 'referenced by a saved selection'
    assert not report['removable']


def test_archive_recipe_without_checksum_or_count_is_not_ready(tmp_path):
    dataset = fixture(tmp_path)
    path = tmp_path / 'registry/datasets/fixture.yaml'
    raw = yaml.safe_load(path.read_text()); raw.update(adapter_config={}, source_url='https://example.org/data'); path.write_text(yaml.safe_dump(raw))
    recipes = tmp_path / 'registry/recipes'; recipes.mkdir()
    (recipes / f'{dataset.id}.yaml').write_text(yaml.safe_dump({
        'adapter': 'json', 'scope': 'Whole release',
        'files': [{'source_name': 'data.json', 'url': 'https://example.org/data.json', 'bytes': 1234, 'format': 'json', 'config_key': 'path'}],
        'allowed_hosts': ['example.org'],
    }))
    plan = PreparationManager(tmp_path).plan(dataset.id, 1_000_000, 1_000_000)
    assert plan['kind'] == 'http_archive' and plan['ready'] is False
    assert any('Checksum not pinned for data.json' in r for r in plan['requirements'])
    assert any('population count must be declared' in r for r in plan['requirements'])
    with pytest.raises(ValueError, match='requirements'):
        PreparationManager(tmp_path).start(plan['id'])


def test_prune_preserves_transitive_source_dependencies_and_running_versions(tmp_path):
    import shutil
    dataset = fixture(tmp_path)
    manager = PreparationManager(tmp_path)
    plan = manager.plan(dataset.id, 1_000_000, 1_000_000)
    run(tmp_path, plan['id'])
    old = Registry(tmp_path).active_directory(dataset.id)
    intermediate = old.parent / 'intermediate'
    newest = old.parent / 'newest'
    shutil.copytree(old, intermediate)
    shutil.copytree(old, newest)
    def dependency(directory, target):
        document = json.loads((directory / 'dataset.json').read_text())
        document['adapter_config']['source_files'] = [{'path': str(target / 'source.bin')}]
        (directory / 'dataset.json').write_text(json.dumps(document))
    dependency(intermediate, old)
    dependency(newest, intermediate)
    (old.parent / 'active.json').write_text(json.dumps({'version': newest.name}))
    running = old.parent / ('f' * 64); running.mkdir()
    (manager.directory / running.name).mkdir()
    (manager.directory / running.name / 'status.json').write_text(json.dumps({'status': 'running'}))
    report = manager.prune(execute=True)
    assert not report['removable']
    assert {x['version'] for x in report['retained']} == {old.name, intermediate.name, newest.name, running.name}
    assert old.exists() and intermediate.exists()


def test_unknown_adapter_recipe_cannot_be_started(tmp_path):
    dataset = fixture(tmp_path)
    recipes = tmp_path / 'registry/recipes'; recipes.mkdir()
    (recipes / f'{dataset.id}.yaml').write_text(yaml.safe_dump({
        'adapter': 'not_implemented', 'scope': 'Full', 'expected_count': 3,
        'files': [{'source_name': 'data.zip', 'url': 'https://example.org/data.zip', 'bytes': 100, 'sha256': 'a'*64}],
    }))
    plan = PreparationManager(tmp_path).plan(dataset.id, 1_000_000, 1_000_000)
    assert not plan['ready']
    assert any('Adapter implementation missing' in reason for reason in plan['requirements'])


def test_selective_parquet_plan_reserves_transfer_budget_instead_of_full_shards(monkeypatch,tmp_path):
    dataset=fixture(tmp_path)
    path=tmp_path/'registry/datasets/fixture.yaml'
    raw=yaml.safe_load(path.read_text());raw.update(adapter_config={},source_url='https://huggingface.co/datasets/owner/repo');path.write_text(yaml.safe_dump(raw))
    monkeypatch.setattr('dataset_atlas.preparation.read_metadata',lambda url:{'sha':'a'*40,'siblings':[
        {'rfilename':'train.parquet','size':4_000_000_000_000,'lfs':{'sha256':'b'*64}}]})
    plan=PreparationManager(tmp_path).plan(dataset.id,100_000_000,100_000_000,source_mode='selective')
    assert plan['ready'] and plan['kind']=='huggingface_remote_columnar'
    assert plan['source_total_bytes']==4_000_000_000_000
    assert plan['expected_download_bytes']==100_000_000 and plan['download_is_upper_bound']
    assert plan['required_free_bytes']==1_120_000_000
    full=PreparationManager(tmp_path).plan(dataset.id,100_000_000,100_000_000)
    assert not full['ready']


def test_multiple_native_archives_repack_and_join_with_shared_output_budget(tmp_path):
    import tarfile, io
    from PIL import Image
    from dataset_atlas.adapters import get_adapter
    image=io.BytesIO();Image.new('RGB',(3,4)).save(image,'PNG')
    config={'annotations':[], 'local_archives':{}, 'repack_paths':[], 'source_files':[]}
    for name in ['first','second']:
        path=tmp_path/(name+'.tgz')
        with tarfile.open(path,'w:gz') as archive:
            data=image.getvalue();entry=tarfile.TarInfo('a.png');entry.size=len(data);archive.addfile(entry,io.BytesIO(data))
        annotations=tmp_path/(name+'.json');annotations.write_text('[{"image":"a.png"}]')
        config[name+'_path']=str(path);config[name+'_annotations']=str(annotations)
        config['annotations'].append({'path_key':name+'_annotations','split':name,'media_paths_field':'image','media_archive':name})
        config['local_archives'][name]={'path_key':name+'_path'};config['repack_paths'].append(name+'_path')
        config['source_files'].append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    dataset=Dataset(id='multi',name='Fixture',release='r',adapter='structured_collection',adapter_config=config,coverage={'total_count':2})
    directory=tmp_path/'registry/datasets';directory.mkdir(parents=True)
    (directory/'multi.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    manager=PreparationManager(tmp_path);plan=manager.plan('multi',10000,1000000);run(tmp_path,plan['id'])
    registry=Registry(tmp_path);prepared=registry.dataset('multi');adapter=get_adapter(prepared)
    source=adapter.prepare(adapter.plan(10,10000));records=adapter.iter_records(source).records
    assert len({r.assets[0].id for r in records})==2
    assert all(adapter.resolve_asset(source,r.assets[0].uri).data==image.getvalue() for r in records)
    receipt=json.loads((registry.active_directory('multi')/'receipt.json').read_text())
    assert len(receipt['derived_sources'])==2
    for item in receipt['derived_sources']:assert item['bytes']>0


def test_new_recipe_replaces_active_source_and_gets_a_new_snapshot(tmp_path, monkeypatch):
    original=fixture(tmp_path,3);manager=PreparationManager(tmp_path)
    initial=manager.plan(original.id,1000000,1000000);run(tmp_path,initial['id'])
    old=Registry(tmp_path).dataset(original.id)
    path=tmp_path/'replacement.json';path.write_text('[{"id":"new","text":"new release"}]')
    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    recipes=tmp_path/'registry/recipes';recipes.mkdir()
    (recipes/(original.id+'.yaml')).write_text(yaml.safe_dump({'adapter':'json','release':'new-release','expected_count':1,
        'scope':'New release','adapter_config':{'mapping':{'id':'id','text':'text'}},'files':[{'url':'https://example.org/new.json',
        'source_name':'new.json','bytes':path.stat().st_size,'sha256':checksum,'config_key':'path','format':'json'}]}))
    plan=manager.plan(original.id,1000000,1000000)
    assert plan['kind']=='http_archive' and plan['expected_count']==1
    assert plan['prepared_dataset']['snapshot_id'] == ''
    monkeypatch.setattr('dataset_atlas.storage.HttpsFetcher.fetch',lambda *args,**kwargs:path)
    run(tmp_path,plan['id']);registry=Registry(tmp_path);new=registry.dataset(original.id)
    assert new.snapshot_id != old.snapshot_id and new.coverage.total_count==1
    assert registry.pack(original.id).records[0].text=='new release'
    assert registry.dataset_version(original.id,old.release).snapshot_id==old.snapshot_id


def test_registered_source_preparation_never_fetches_network(tmp_path,monkeypatch):
    from dataset_atlas.storage.sources import register_source
    dataset=fixture(tmp_path,2);path=tmp_path/'replacement.json';path.write_text('[{"text":"registered"}]')
    sha=hashlib.sha256(path.read_bytes()).hexdigest();register_source(tmp_path,path,sha,1000)
    recipes=tmp_path/'registry/recipes';recipes.mkdir()
    (recipes/(dataset.id+'.yaml')).write_text(yaml.safe_dump({'adapter':'json','release':'registered','expected_count':1,'scope':'Fixture',
        'adapter_config':{'mapping':{'text':'text'}},'files':[{'source_name':'data.json','url':'https://example.org/data.json','sha256':sha,'bytes':path.stat().st_size,'format':'json','config_key':'path'}]}))
    def reject(*a,**kw):raise AssertionError('Registered source was downloaded again')
    monkeypatch.setattr('dataset_atlas.storage.HttpsFetcher.fetch',reject)
    manager=PreparationManager(tmp_path);plan=manager.plan(dataset.id,10000,1000000);run(tmp_path,plan['id'])
    assert Registry(tmp_path).pack(dataset.id).records[0].text=='registered'


def test_gated_recipe_requires_local_credentials_without_serializing_them(tmp_path, monkeypatch):
    dataset = fixture(tmp_path, 3)
    recipes = tmp_path/'registry/recipes'; recipes.mkdir()
    source = tmp_path/'source.parquet'
    (recipes/(dataset.id+'.yaml')).write_text(yaml.safe_dump({
        'credential_profile': 'huggingface', 'release': 'new', 'scope': 'fixture', 'expected_count': 3,
        'files': [{'url': 'https://huggingface.co/datasets/fixture/data.parquet', 'source_name': 'data.parquet',
                   'bytes': source.stat().st_size, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]}))
    monkeypatch.delenv('HF_TOKEN', raising=False)
    monkeypatch.setenv('HF_TOKEN_PATH', str(tmp_path/'missing-token'))
    manager = PreparationManager(tmp_path)
    plan = manager.plan(dataset.id, 1000000, 1000000)
    assert not plan['ready'] and any('credentials are missing' in item for item in plan['requirements'])
    monkeypatch.setenv('HF_TOKEN', 'hf_fixture_private')
    plan = manager.plan(dataset.id, 1000000, 1000000)
    assert plan['ready'] and plan['credential_profile'] == 'huggingface'
    assert 'hf_fixture_private' not in json.dumps(plan)


def test_prune_does_not_claim_to_free_a_source_linked_outside_prepared(tmp_path):
    dataset = fixture(tmp_path)
    manager = PreparationManager(tmp_path)
    source = tmp_path/'work/source-objects/native'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'z'*4096)
    failed = tmp_path/'work/prepared'/dataset.id/('f'*64)
    failed.mkdir(parents=True)
    os.link(source,failed/'archive.zip')
    report = manager.prune()
    entry = next(item for item in report['removable'] if item['version']==failed.name)
    assert entry['freed_bytes']==0
    manager.prune(execute=True)
    assert not failed.exists() and source.read_bytes()==b'z'*4096


def test_recipe_resource_limits_are_pinned_and_passed_to_dispatch(tmp_path,monkeypatch):
    dataset=fixture(tmp_path,3);recipes=tmp_path/'registry/recipes';recipes.mkdir()
    path=recipes/f'{dataset.id}.yaml';path.write_text(yaml.safe_dump({'resource_limits':{'max_wall_seconds':21600,'max_cpu_seconds':7200}}))
    manager=PreparationManager(tmp_path);plan=manager.plan(dataset.id,1000000,1000000)
    assert plan['resource_limits']=={'max_rss_bytes':8000000000,'max_wall_seconds':21600,'max_cpu_seconds':7200}
    observed=[]
    from dataset_atlas.jobs import limits
    def dispatch(command,config):
        observed.append(config)
        raise RuntimeError('test-only dispatch observation')
    monkeypatch.setattr(limits,'worker_command',dispatch)
    with pytest.raises(RuntimeError,match='dispatch observation'):manager.start(plan['id'])
    assert observed==[plan['resource_limits']]
    path.write_text(yaml.safe_dump({'resource_limits':{'max_wall_seconds':0}}))
    with pytest.raises(ValueError,match='positive integer'):manager.plan(dataset.id,1000000,1000000)


def test_failed_snapshot_writer_closes_input_iterator(tmp_path,monkeypatch):
    dataset=fixture(tmp_path,3);manager=PreparationManager(tmp_path)
    plan=manager.plan(dataset.id,1000000,1000000);retained=[]
    def fail(records,*args,**kwargs):
        retained.append(records)
        next(records)
        raise ValueError('deliberate downstream writer failure')
    monkeypatch.setattr('dataset_atlas.queries.parquet.build_parquet_snapshot',fail)
    with pytest.raises(ValueError,match='downstream writer failure'):run(tmp_path,plan['id'])
    assert retained[0].gi_frame is None
    assert manager.status(plan['id'])['status']=='failed'
