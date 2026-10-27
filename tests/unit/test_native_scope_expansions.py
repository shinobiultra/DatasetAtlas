"""Synthetic checks only: these do not establish native dataset coverage."""
import csv
import hashlib
import io
import json
from pathlib import Path

from PIL import Image
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from dataset_atlas.adapters.structured_collection import StructuredCollectionAdapter
from dataset_atlas.converters.media import hc_bench, hc_bench_complete
from dataset_atlas.models import Dataset
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run
from dataset_atlas.adapters.core import StructuredAdapter


def test_unacquired_native_media_retains_exact_path_without_a_usable_uri(tmp_path):
    path = tmp_path / 'annotations.json'
    path.write_text(json.dumps([{'video': 'clip_1.mp4', 'question': 'Synthetic?', 'candidates': ['a', 'b']}]))
    dataset = Dataset(id='native-fixture', name='Native fixture', release='r', snapshot_id='s',
        adapter='structured_collection', adapter_config={'path': str(path),
        'annotations': [{'path_key': 'path', 'split': 'task', 'choices_field': 'candidates',
            'unavailable_media': {'path_field': 'video', 'modality': 'video', 'availability': 'not_acquired',
                                  'source_url': 'https://example.org/native'}}],
        'mapping': {'question': 'question', 'choices': '_atlas_choices'}})
    adapter = StructuredCollectionAdapter(dataset)
    record = adapter.iter_records(adapter.prepare(adapter.plan(1, 10000))).records[0]
    assert record.source['video'] == 'clip_1.mp4' and record.choices == ['a', 'b']
    assert record.assets[0].uri is None
    assert record.assets[0].metadata['source_path'] == 'clip_1.mp4'
    assert record.assets[0].metadata['availability'] == 'not_acquired'
    assert '_atlas_unavailable_media' not in record.source
    assert '_atlas_collection_unacquired_media' not in record.source
    adapter.config['annotations'][0]['unavailable_media']['availability'] = 'absent_from_pinned_release'
    del adapter._annotation_rows
    with pytest.raises(ValueError, match='not_acquired'):adapter.count


def test_hc_native_inventory_preserves_order_folders_and_original_bytes(tmp_path):
    payload = io.BytesIO(); Image.new('RGB', (3, 2), 'blue').save(payload, 'PNG')
    image = payload.getvalue(); source = tmp_path / 'source.png'; source.write_bytes(image)
    params = {'native_files': [{'key': 'second', 'path': 'text/Latin/second.png'},
                               {'key': 'first', 'path': 'object/hidden/first.png'}]}
    result = hc_bench(params, {'first': source, 'second': source}, tmp_path / 'out', lambda: None)
    rows = list(csv.DictReader(result['path'].open()))
    assert [row['path'] for row in rows] == ['text/Latin/second.png', 'object/hidden/first.png']
    assert rows[0]['source_subset'] == 'text/Latin'
    for row in rows:
        assert (result['media_dir'] / row['path']).read_bytes() == image
        assert row['source_sha256'] == hashlib.sha256(image).hexdigest()
    params['native_files'][1]['path'] = params['native_files'][0]['path']
    with pytest.raises(ValueError, match='duplicate'):hc_bench(params, {'first': source, 'second': source}, tmp_path / 'bad', lambda: None)


def local_fixture(root):
    source = root / 'source.parquet'
    pq.write_table(pa.table({'text': ['synthetic a', 'synthetic b']}), source)
    dataset = Dataset(id='candidate-fixture', name='Candidate fixture', release='r', snapshot_id='s',
        adapter='columnar', adapter_config={'files': [{'path': str(source),
        'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]}, coverage={'total_count': 2})
    path = root / 'registry/datasets/candidate.yaml'; path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    return PreparationManager(root), dataset.id


def test_hc_complete_keeps_independent_annotation_rows_and_passive_text(tmp_path):
    payload = io.BytesIO(); Image.new('RGB', (3, 2), 'blue').save(payload, 'PNG')
    image = tmp_path / 'image.png'; image.write_bytes(payload.getvalue())
    annotations = tmp_path / 'annotations.json'
    native = [{'Lemma': 'unmatched second'}, {'Lemma': 'unmatched first'}]
    annotations.write_text(json.dumps(native))
    passive = tmp_path / 'prompts.txt'; passive.write_text('synthetic instructions\n')
    params = {'native_files': [{'key': 'image', 'path': 'wild/image.png'}],
        'native_annotations': [{'key': 'annotations', 'path': 'object/labels.json'}],
        'native_texts': [{'key': 'passive', 'path': 'object/prompts.txt'}]}
    result = hc_bench_complete(params, {'image': image, 'annotations': annotations, 'passive': passive}, tmp_path/'out', lambda: None)
    records = [json.loads(line) for line in result['path'].read_text().splitlines()]
    assert [row['unit_kind'] for row in records] == ['image', 'annotation', 'annotation', 'source_document']
    assert [row['native_annotation'] for row in records[1:3]] == native
    assert all('path' not in row for row in records[1:])
    assert records[-1]['text'] == passive.read_text()


def test_candidate_preparation_preserves_existing_pointer_and_retry_intent(tmp_path):
    manager, dataset_id = local_fixture(tmp_path)
    initial = manager.plan(dataset_id, 1_000_000, 1_000_000)
    run(tmp_path, initial['id'])
    pointer = tmp_path / 'work/prepared' / dataset_id / 'active.json'
    plan = manager.plan(dataset_id, 1_000_000, 1_100_000)
    before = pointer.read_bytes()
    status = manager._path(plan['id']) / 'status.json'
    status.write_text(json.dumps({'status': 'failed', 'activate_on_success': False}))
    run(tmp_path, plan['id'])
    assert pointer.read_bytes() == before
    result = json.loads(status.read_text())
    assert result['status'] == 'completed' and result['activate_on_success'] is False
    assert (pointer.parent / plan['id'] / 'snapshot/manifest.json').is_file()


def test_default_preparation_still_activates(tmp_path):
    manager, dataset_id = local_fixture(tmp_path)
    plan = manager.plan(dataset_id, 1_000_000, 1_000_000)
    run(tmp_path, plan['id'])
    pointer = tmp_path / 'work/prepared' / dataset_id / 'active.json'
    assert json.loads(pointer.read_text())['version'] == plan['id']


def test_retained_native_media_requires_exact_binding_and_unchanged_bytes(tmp_path):
    payload = io.BytesIO(); Image.new('RGB', (3, 2), 'blue').save(payload, 'PNG')
    image = tmp_path/'retained.png'; image.write_bytes(payload.getvalue())
    sha = hashlib.sha256(image.read_bytes()).hexdigest()
    annotations = tmp_path/'rows.json'; annotations.write_text(json.dumps([{'image': 'native.png'}, {'image': 'other.png'}]))
    dataset = Dataset(id='retained-fixture', name='Retained fixture', release='r', snapshot_id='s',
        adapter='structured_collection', adapter_config={'path':str(annotations),
        'annotations':[{'path_key':'path','split':'task','unavailable_media':
            {'path_field':'image','modality':'image','availability':'not_acquired'}}],
        'retained_media_root':str(tmp_path),
        'retained_media':{'["task","native.png"]':{'path':image.name,'bytes':image.stat().st_size,'sha256':sha}},
        'retained_media_max_bytes':10000})
    adapter=StructuredCollectionAdapter(dataset)
    validation=adapter.validate_media(10000)
    assert validation['retained_original_assets']==1 and validation['metadata_bytes_fetched']==0
    source=adapter.prepare(adapter.plan(2,10000));records=adapter.iter_records(source).records
    assert records[0].assets[0].uri=='retained/'+sha
    assert records[1].assets[0].uri is None
    assert adapter.resolve_asset(source,records[0].assets[0].uri).data==image.read_bytes()
    image.write_bytes(b'changed')
    with pytest.raises(ValueError,match='checksum or size'):adapter.resolve_asset(source,records[0].assets[0].uri)


def test_available_preview_eligibility_preserves_complete_native_population(tmp_path):
    payload=io.BytesIO();Image.new('RGB',(3,2),'blue').save(payload,'PNG')
    (tmp_path/'image.png').write_bytes(payload.getvalue())
    source=tmp_path/'records.jsonl'
    rows=[{'id':i,'path':'image.png' if i<100 else None,'text':f'synthetic {i}'} for i in range(105)]
    source.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    dataset=Dataset(id='eligible-fixture',name='Eligible fixture',release='r',snapshot_id='s',adapter='structured',
        adapter_config={'path':str(source),'format':'jsonl','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'media_root':str(tmp_path),'mapping':{'id':'id','text':'text','media':'path'},
            'preview_group_by':'example','preview_available_media_only':True},coverage={'total_count':105})
    registry=tmp_path/'registry/datasets';registry.mkdir(parents=True)
    (registry/'eligible.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    manager=PreparationManager(tmp_path);plan=manager.plan(dataset.id,1_000_000,2_000_000)
    run(tmp_path,plan['id'],activate=False)
    version=tmp_path/'work/prepared'/dataset.id/plan['id']
    pack=json.loads((version/'pack/pack.json').read_text())
    assert len(pack['records'])==100 and all(record['assets'] for record in pack['records'])
    assert pack['sampling']['population_count']==105 and pack['sampling']['eligible_population_count']==100
    assert json.loads((version/'snapshot/manifest.json').read_text())['record_count']==105


def test_manager_retry_keeps_nonactivation_after_restart(tmp_path, monkeypatch):
    manager,dataset_id=local_fixture(tmp_path)
    plan=manager.plan(dataset_id,1_000_000,1_000_000)
    status=manager._path(plan['id'])/'status.json'
    status.write_text(json.dumps({'status':'failed','activate_on_success':False}))
    commands=[]
    class Process:
        pid=0
        def poll(self):return None
    def dispatch(command, **kwargs):
        commands.append(command)
        return Process()
    monkeypatch.setattr('dataset_atlas.preparation.subprocess.Popen',dispatch)
    monkeypatch.setattr('dataset_atlas.jobs.limits.worker_command',lambda command,limits:command)
    for _ in range(2):
        restarted=PreparationManager(tmp_path)
        result=restarted.start(plan['id'])
        assert result['activate_on_success'] is False and commands[-1][-1]=='--no-activate'
        status.write_text(json.dumps({**result,'status':'failed'}))
    assert not (tmp_path/'work/prepared'/dataset_id/'active.json').exists()


@pytest.mark.parametrize(('codec','media_type'), [('JPEG','image/jpeg'), ('WEBP','image/webp')])
def test_native_misnamed_image_preserves_bytes_path_and_verified_actual_mime(tmp_path,codec,media_type):
    payload=io.BytesIO();Image.new('RGB',(3,2),'blue').save(payload,codec)
    image=tmp_path/'native.png';image.write_bytes(payload.getvalue())
    params={'native_files':[{'key':'image','path':'object/hidden/native.png'}],
            'native_extension_exceptions':['object/hidden/native.png']}
    conversion=hc_bench_complete(params,{'image':image},tmp_path/'out',lambda:None)
    dataset=Dataset(id='mime-fixture',name='MIME fixture',release='r',snapshot_id='s',adapter='structured',
        adapter_config={**conversion['adapter_config'],'path':str(conversion['path']),'format':'jsonl',
                        'sha256':conversion['file_sha256'],'media_root':str(conversion['media_dir'])})
    adapter=StructuredAdapter(dataset);source=adapter.prepare(adapter.plan(1,10000))
    record=adapter.iter_records(source).records[0]
    assert record.assets[0].uri=='object/hidden/native.png'
    handle=adapter.resolve_asset(source,record.assets[0].uri)
    assert handle.data==image.read_bytes() and handle.media_type==media_type
    adapter.config['media_type_overrides'][record.assets[0].uri]['sha256']='0'*64
    with pytest.raises(ValueError,match='header or SHA-256'):adapter.resolve_asset(source,record.assets[0].uri)
