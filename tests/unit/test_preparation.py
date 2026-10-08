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


def test_reservation_subtracts_only_owned_allocated_bytes(tmp_path):
    import os
    fixture(tmp_path,1);manager=PreparationManager(tmp_path)
    plan={'id':'a'*64,'dataset_id':'fixture','required_free_bytes':1000000}
    version=tmp_path/'work/prepared/fixture'/plan['id'];version.mkdir(parents=True)
    owned=version/'owned';owned.write_bytes(b'o'*10000)
    shared=version/'shared';shared.write_bytes(b's'*20000);os.link(shared,tmp_path/'source-copy')
    (version/'symlink').symlink_to(tmp_path/'source-copy')
    assert manager._allocated_preparation_bytes(plan)==owned.stat().st_blocks*512
    assert manager._allocated_preparation_bytes({'required_free_bytes':1000000})==0


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


def test_retry_preserves_failed_attempt_and_resource_receipt(tmp_path, monkeypatch):
    dataset=fixture(tmp_path,1); manager=PreparationManager(tmp_path)
    plan=manager.plan(dataset.id,1000000,1000000); directory=manager._path(plan['id'])
    prior={'id':plan['id'],'dataset_id':dataset.id,'status':'failed','error':'retained failure','updated_at':1}
    (directory/'status.json').write_text(json.dumps(prior))
    (directory/'worker.log').write_bytes(b'failed output\n')
    (directory/'resource-error.receipt').write_text(json.dumps({'message':'memory limit'}))
    class Process:
        pid=0
        def __init__(self,*args,**kwargs):pass
        def poll(self):return None
    monkeypatch.setattr('dataset_atlas.preparation.subprocess.Popen',Process)
    manager.start(plan['id'])
    history=list((directory/'attempts').glob('*.json'));assert len(history)==1
    receipt=json.loads(history[0].read_text())
    assert receipt['status']==prior and receipt['resource_error']=={'message':'memory limit'}
    assert receipt['worker_log_bytes_before_retry']==len(b'failed output\n')
    assert receipt['plan_sha256']==hashlib.sha256((directory/'plan.json').read_bytes()).hexdigest()


def test_old_manager_exit_does_not_override_live_retry(tmp_path):
    dataset=fixture(tmp_path,1);manager=PreparationManager(tmp_path)
    plan=manager.plan(dataset.id,1000000,1000000);directory=manager._path(plan['id'])
    prior={'id':plan['id'],'dataset_id':dataset.id,'status':'running','pid':123,'updated_at':1}
    (directory/'status.json').write_text(json.dumps(prior))
    class OldProcess:
        pid=456
        def poll(self):return 0
    manager.processes[plan['id']]=OldProcess()
    # Use a recent queued state before the replacement worker writes its PID.
    import time
    prior.update(status='queued',updated_at=time.time());prior.pop('pid')
    (directory/'status.json').write_text(json.dumps(prior))
    assert manager.status(plan['id'])['status']=='queued'


def test_transfer_keeps_records_ids_and_hashes_and_preserves_donor(tmp_path):
    import shutil
    from dataset_atlas.preparation.transfer import import_prepared_version
    donor=tmp_path/'donor';donor.mkdir();dataset=fixture(donor,117)
    manager=PreparationManager(donor);plan=manager.plan(dataset.id,1000000,1000000);run(donor,plan['id'])
    original=Registry(donor).active_directory(dataset.id)
    native=original/'sources/native.parquet';native.parent.mkdir();shutil.copy2(donor/'source.parquet',native)
    metadata=json.loads((original/'dataset.json').read_text())
    metadata['adapter_config']['files'][0]['path']=str(native)
    metadata['adapter_config']['source_files']=[{'path':str(native),'sha256':hashlib.sha256(native.read_bytes()).hexdigest()}]
    (original/'dataset.json').write_text(json.dumps(metadata))
    recipient=tmp_path/'recipient';shutil.copytree(donor/'registry',recipient/'registry')
    donor_bytes=(original/'dataset.json').read_bytes()
    proof=import_prepared_version(recipient,donor,dataset.id)
    imported=Registry(recipient).active_directory(dataset.id)
    assert proof['records_unchanged'] and Registry(recipient).dataset(dataset.id).snapshot_id==Registry(donor).dataset(dataset.id).snapshot_id
    assert Registry(recipient).pack(dataset.id).records==Registry(donor).pack(dataset.id).records
    assert (original/'dataset.json').read_bytes()==donor_bytes
    assert json.loads((imported/'dataset.json').read_text())['adapter_config']['files'][0]['path']==str(imported/'sources/native.parquet')
    assert (imported/'snapshot/records.parquet').stat().st_ino==(original/'snapshot/records.parquet').stat().st_ino
    with pytest.raises(ValueError,match='already holds'):import_prepared_version(recipient,donor,dataset.id)


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
    cache_roots=[]
    def fetch(_fetcher, _url, cache, _identity, **kwargs):
        cache_roots.append(cache.root)
        return path
    monkeypatch.setattr('dataset_atlas.storage.HttpsFetcher.fetch',fetch)
    run(tmp_path,plan['id']);registry=Registry(tmp_path);new=registry.dataset(original.id)
    assert new.snapshot_id != old.snapshot_id and new.coverage.total_count==1
    assert registry.pack(original.id).records[0].text=='new release'
    assert registry.dataset_version(original.id,old.release).snapshot_id==old.snapshot_id
    assert cache_roots==[registry.active_directory(original.id)/'staging-download-cache']
    assert not cache_roots[0].exists()
    assert Path(new.adapter_config['path']).read_bytes()==path.read_bytes()


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


def test_completed_authorized_metadata_preserves_gate_and_publication_rights():
    from dataset_atlas.models import Dataset
    from dataset_atlas.preparation import prepared_metadata
    dataset = Dataset(id='authorized', name='Authorized native population', release='pinned',
        adapter='remote_columnar', adapter_config={'credential_profile':'huggingface'},
        coverage={'access':'gated','blockers':[
            'Original-source credentials or agreement are required.',
            'Source-image redistribution rights remain unreviewed.']})
    result = prepared_metadata(dataset, 'Successful authorized native preparation')
    assert result.coverage.access == 'gated'
    assert result.coverage.blockers == ['Source-image redistribution rights remain unreviewed.']
    assert result.coverage.publication == 'not_reviewed'
    uncredentialed = Dataset(id='uncredentialed', name='Uncredentialed', release='pinned',
        coverage={'blockers':['Original-source credentials or agreement are required.']})
    assert prepared_metadata(uncredentialed, 'Unrelated source').coverage.blockers == uncredentialed.coverage.blockers


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


def test_selective_worker_uses_the_cache_budget_and_root_that_were_admitted(tmp_path, monkeypatch):
    dataset = fixture(tmp_path, 3)
    path = tmp_path/'registry/datasets/fixture.yaml'
    raw = yaml.safe_load(path.read_text())
    raw.update(adapter_config={'remote_cache_root': 'work/custom-cache', 'remote_cache_bytes': 123456},
               source_url='https://huggingface.co/datasets/owner/repo')
    path.write_text(yaml.safe_dump(raw))
    payload = (tmp_path/'source.parquet').read_bytes()
    monkeypatch.setattr('dataset_atlas.preparation.read_metadata', lambda url: {'sha': 'a'*40, 'siblings': [
        {'rfilename': 'train.parquet', 'size': len(payload), 'lfs': {'sha256': hashlib.sha256(payload).hexdigest()}}]})
    monkeypatch.setattr('dataset_atlas.preparation.remote.range_fingerprint', lambda *args, **kwargs: '"fixture"')
    monkeypatch.setattr('dataset_atlas.storage.ranges.HttpsRangeReader._fetch', lambda self, start, end: payload[start:end+1])
    manager = PreparationManager(tmp_path)
    plan = manager.plan(dataset.id, 1000000, 1000000, source_mode='selective')
    assert plan['required_free_bytes'] == 1000000 + 123456 + 20000000
    run(tmp_path, plan['id'])
    prepared = Registry(tmp_path).dataset(dataset.id)
    assert prepared.adapter_config['remote_cache_bytes'] == 123456
    assert prepared.adapter_config['remote_cache_root'] == str(tmp_path/'work/custom-cache')
    assert (tmp_path/'work/custom-cache/cache.sqlite3').is_file()


@pytest.mark.parametrize('invalid', [0, -1, True, 1.5])
def test_invalid_remote_cache_budget_cannot_reduce_reservation(tmp_path, monkeypatch, invalid):
    dataset = fixture(tmp_path, 3)
    path = tmp_path/'registry/datasets/fixture.yaml'
    raw = yaml.safe_load(path.read_text())
    raw.update(adapter_config={'remote_cache_bytes': invalid}, source_url='https://huggingface.co/datasets/owner/repo')
    path.write_text(yaml.safe_dump(raw))
    monkeypatch.setattr('dataset_atlas.preparation.read_metadata', lambda url: {'sha': 'a'*40, 'siblings': [
        {'rfilename': 'train.parquet', 'size': 100, 'lfs': {'sha256': 'b'*64}}]})
    with pytest.raises(ValueError, match='cache budget'):
        PreparationManager(tmp_path).plan(dataset.id, 1000000, 1000000, source_mode='selective')


def registered_recipe_fixture(tmp_path):
    from dataset_atlas.storage.sources import register_source
    dataset = fixture(tmp_path, 3)
    payload = (tmp_path/'source.parquet').read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    registered = register_source(tmp_path, tmp_path/'source.parquet', sha, len(payload))
    recipes = tmp_path/'registry/recipes'; recipes.mkdir()
    (recipes/(dataset.id+'.yaml')).write_text(yaml.safe_dump({'adapter':'structured', 'expected_count':3, 'scope':'Fixture only',
        'files':[{'source_name':'rows.parquet','url':'https://example.org/rows.parquet','bytes':len(payload),'sha256':sha,
                  'format':'parquet','config_key':'path'}], 'adapter_config':{'format':'parquet'}}))
    return dataset, Path(registered['path'])


def test_registered_original_reserves_only_output_and_is_hardlinked(tmp_path):
    dataset, original = registered_recipe_fixture(tmp_path)
    manager = PreparationManager(tmp_path)
    plan = manager.plan(dataset.id, 1000000, 1000000)
    assert plan['reuse_registered_sources'] == ['rows.parquet']
    assert plan['required_free_bytes'] == 1000000
    run(tmp_path, plan['id'])
    target = Path(Registry(tmp_path).dataset(dataset.id).adapter_config['path'])
    assert target.stat().st_ino == original.stat().st_ino


@pytest.mark.parametrize('failure', ['missing', 'link_failure'])
def test_reserved_original_reuse_never_falls_back_to_unreserved_download_or_copy(tmp_path, monkeypatch, failure):
    dataset, original = registered_recipe_fixture(tmp_path)
    manager = PreparationManager(tmp_path)
    plan = manager.plan(dataset.id, 1000000, 1000000)
    def forbidden(*args, **kwargs):
        raise AssertionError('Unreserved download/copy must never occur')
    monkeypatch.setattr('dataset_atlas.storage.HttpsFetcher.fetch', forbidden)
    monkeypatch.setattr('dataset_atlas.preparation.worker.shutil.copy2', forbidden)
    if failure == 'missing':
        original.unlink()
    else:
        def fail_link(*args):
            raise OSError('Fixture disallows hard links')
        monkeypatch.setattr('dataset_atlas.preparation.worker.os.link', fail_link)
    with pytest.raises(ValueError, match='create a new plan'):
        run(tmp_path, plan['id'])
    assert Registry(tmp_path).active_directory(dataset.id) is None


@pytest.mark.parametrize('selected_count',[3,4])
def test_native_class_group_index_preserves_labels_and_checks_actual_membership(tmp_path,selected_count):
    dataset=fixture(tmp_path,5);path=tmp_path/'source.parquet'
    pq.write_table(pa.table({'label':pa.array([150,151,268,269,281],type=pa.int32()),'text':['native']*5}),path)
    dataset.adapter_config['files'][0]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    dataset.coverage.total_count=selected_count
    dataset.adapter_config.update(expected_source_count=5,record_filter={'native_class_groups':{'field':'label',
        'groups':[{'name':'Dog','start':151,'end':268},{'name':'Cat','start':281,'end':285}],'provenance':{'revision':'fixture-author'}}})
    (tmp_path/'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    manager=PreparationManager(tmp_path);plan=manager.plan(dataset.id,1_000_000,1_000_000)
    if selected_count==4:
        with pytest.raises(ValueError,match='Snapshot has 3 records; expected 4'):run(tmp_path,plan['id'])
        assert manager.status(plan['id'])['status']=='failed' and Registry(tmp_path).active_directory(dataset.id) is None
    else:
        run(tmp_path,plan['id'])
        reg=Registry(tmp_path);pack=reg.pack(dataset.id)
        assert manager.status(plan['id'])['status']=='completed' and len(pack.records)==3
        assert {r.source['label'] for r in pack.records}=={151,268,281}
        assert {r.source['_atlas_native_class_group']['id'] for r in pack.records}=={0,1}
        assert any(f.id=='source._atlas_native_class_group' for f in pack.fields)


def test_a_recipe_that_downloads_preview_originals_states_that_transfer_in_its_plan(tmp_path):
    """Regression: a plan advertised a 4.6 MB download for a dataset whose 100 preview originals really transfer 5.2 GB, so a 2 GB budget failed midway."""
    dataset = fixture(tmp_path)
    recipes = tmp_path / 'registry/recipes'; recipes.mkdir()
    (recipes / f'{dataset.id}.yaml').write_text(yaml.safe_dump({
        'adapter': dataset.adapter, 'scope': 'Full', 'expected_count': 3, 'preview_media_transfer_bytes': 5_300_000_000,
        'files': [{'source_name': 'data.csv', 'url': 'https://example.org/data.csv', 'bytes': 4_600_000, 'sha256': 'a' * 64, 'format': 'csv', 'config_key': 'path'}],
        'allowed_hosts': ['example.org'],
    }))
    small = PreparationManager(tmp_path).plan(dataset.id, 2_000_000_000, 1_000_000_000)
    assert small['expected_download_bytes'] == 4_600_000 + 5_300_000_000 and small['download_is_upper_bound']
    assert small['preview_media_transfer_bytes'] == 5_300_000_000 and not small['ready']
    assert any('exceeds the selected download budget' in reason for reason in small['requirements'])
    large = PreparationManager(tmp_path).plan(dataset.id, 6_000_000_000, 1_000_000_000)
    assert 'exceeds the selected download budget' not in ' '.join(large['requirements'])
    with pytest.raises(ValueError, match='preview_media_transfer_bytes'):
        (recipes / f'{dataset.id}.yaml').write_text(yaml.safe_dump({
            'adapter': dataset.adapter, 'scope': 'Full', 'expected_count': 3, 'preview_media_transfer_bytes': -1,
            'files': [{'source_name': 'data.csv', 'url': 'https://example.org/data.csv', 'bytes': 1, 'sha256': 'a' * 64, 'format': 'csv', 'config_key': 'path'}],
            'allowed_hosts': ['example.org']}))
        PreparationManager(tmp_path).plan(dataset.id, 1_000_000, 1_000_000)


def test_a_recipe_can_make_auto_choose_selective_reads_over_a_small_complete_download(tmp_path, monkeypatch):
    """Regression: ZeroBench's 95 MB shard is small enough for auto to download completely, but its embedded images exceed the full-download limit;
    only the selective route reproduces the maintainer's preview from an empty workspace."""
    dataset = fixture(tmp_path)
    recipes = tmp_path / 'registry/recipes'; recipes.mkdir()
    modes = []

    def fake_plan(self, dataset_id, max_download_bytes, max_output_bytes, source_mode='download'):
        modes.append(source_mode)
        return {'ready': True, 'expected_download_bytes': 1_000, 'source_mode': source_mode}

    monkeypatch.setattr(PreparationManager, '_plan', fake_plan)
    manager = PreparationManager(tmp_path)
    assert manager.plan(dataset.id, 1_000_000, 1_000_000, 'auto')['source_mode'] == 'download'
    (recipes / f'{dataset.id}.yaml').write_text(yaml.safe_dump({'auto_source_mode': 'selective'}))
    assert manager.plan(dataset.id, 1_000_000, 1_000_000, 'auto')['source_mode'] == 'selective'
    assert manager.plan(dataset.id, 1_000_000, 1_000_000, 'download')['source_mode'] == 'download'
    (recipes / f'{dataset.id}.yaml').write_text(yaml.safe_dump({'auto_source_mode': 'sample'}))
    with pytest.raises(ValueError, match='auto_source_mode'):
        manager.plan(dataset.id, 1_000_000, 1_000_000, 'auto')


def test_running_writer_lease_survives_an_invisible_pid(tmp_path):
    from dataset_atlas.preparation.slots import try_writer_slot
    dataset=fixture(tmp_path,1);manager=PreparationManager(tmp_path)
    plan=manager.plan(dataset.id,1000000,1000000);directory=manager._path(plan['id'])
    state={'id':plan['id'],'dataset_id':dataset.id,'status':'running','pid':999999999,'updated_at':1}
    (directory/'status.json').write_text(json.dumps(state))
    lease=try_writer_slot(manager.directory,dataset.id,plan['id'])
    assert lease is not None
    with lease:
        assert manager.status(plan['id'])['status']=='running'
    assert manager.status(plan['id'])['status']=='interrupted'


def test_another_plan_lease_does_not_keep_a_dead_plan_running(tmp_path):
    from dataset_atlas.preparation.slots import try_writer_slot
    dataset=fixture(tmp_path,1);manager=PreparationManager(tmp_path)
    plan=manager.plan(dataset.id,1000000,1000000);directory=manager._path(plan['id'])
    state={'id':plan['id'],'dataset_id':dataset.id,'status':'running','pid':999999999,'updated_at':1}
    (directory/'status.json').write_text(json.dumps(state))
    lease=try_writer_slot(manager.directory,dataset.id,'different-plan')
    assert lease is not None
    with lease: assert manager.status(plan['id'])['status']=='interrupted'


def test_compact_atomic_pack_preserves_unicode_types_and_native_envelopes(tmp_path):
    from dataset_atlas.preparation import atomic
    value={'dataset':{'id':'generated','name':'日本語'},'records':[{'id':'generated-a','source':{'integer':7,'boolean':False,'missing':None,'float':-0.0,'nested':[{'_atlas_native_type':'float64','ieee754_hex':'7ff8000000000012'}]}}]}
    target=tmp_path/'pack.json';atomic(target,value,compact=True)
    actual=json.loads(target.read_text())
    assert actual==value and type(actual['records'][0]['source']['integer']) is int and type(actual['records'][0]['source']['boolean']) is bool
    assert target.stat().st_size<len(json.dumps(value,indent=2,ensure_ascii=False).encode())
