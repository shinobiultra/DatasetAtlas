"""Synthetic converter/reader checks, separate from native replay evidence."""
import hashlib
import io
import json
from pathlib import Path

from PIL import Image
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from dataset_atlas.adapters import get_adapter
from dataset_atlas.converters import run_conversion
from dataset_atlas.converters.retained_visuals import retained_visual_parquet, retained_visual_image_jsonl
from dataset_atlas.models import Dataset
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run
from dataset_atlas.storage.sources import register_source


def image(color):
    stream=io.BytesIO();Image.new('RGB',(4,3),color).save(stream,'PNG');return stream.getvalue()


def original(tmp_path):
    path=tmp_path/'original.parquet'
    pq.write_table(pa.Table.from_pylist([
        {'example_id':'first','prompt':'Synthetic first?','image':{'bytes':image('red'),'path':'first.png'}},
        {'example_id':'second','prompt':'Synthetic second?','image':{'bytes':image('blue'),'path':'second.png'}},
    ]),path)
    return path


def test_jsonl_media_stays_lazy_and_preserves_native_hash_paths(tmp_path,monkeypatch):
    path=original(tmp_path)
    def no_decode(*args,**kwargs):raise AssertionError('Conversion must not decode images')
    with monkeypatch.context() as context:
        context.setattr(Image,'open',no_decode)
        conversion=retained_visual_image_jsonl({}, {'source':path},tmp_path/'out',lambda:None,max_output_bytes=10000)
    rows=[json.loads(line) for line in conversion['path'].read_text().splitlines()]
    assert rows[0]['source_image_path']=='first.png' and rows[0]['example_id']=='first'
    assert rows[0]['media_path']=='images/'+hashlib.sha256(image('red')).hexdigest()+'.png'
    assert not (tmp_path/'out/media').exists()
    dataset=Dataset(id='fixture',name='Fixture',release='r',snapshot_id='s',adapter='retained_parquet_media',
        adapter_config={'path':str(conversion['path']),'format':'jsonl','sha256':conversion['file_sha256'],
            'mapping':{'id':'example_id','question':'prompt','media':'media_path'},**conversion['adapter_config']})
    adapter=get_adapter(dataset);source=adapter.prepare(adapter.plan(2,100000))
    records=adapter.iter_records(source).records
    assert records[0].question=='Synthetic first?'
    assert adapter.resolve_asset(source,records[0].assets[0].uri).data==image('red')
    adapter.config['original_media_rows'][records[0].assets[0].uri]=1
    with pytest.raises(ValueError,match='canonical SHA-256'):adapter.resolve_asset(source,records[0].assets[0].uri)
    adapter.config['original_media_rows'][records[0].assets[0].uri]=0
    path.write_bytes(b'x'*path.stat().st_size)
    with pytest.raises(ValueError,match='checksum changed'):adapter.resolve_asset(source,records[0].assets[0].uri)


def test_binary_parquet_and_jsonl_sinks_refuse_before_the_reservation_is_crossed(tmp_path):
    source=original(tmp_path)
    params={'mode':'realworldqa','sources':[{'key':'source','native_path':'test.parquet'}]}
    spec={'name':'retained_visual_parquet','params':params,'count':2,'rows_sha256':'0'*64}
    with pytest.raises(ValueError,match='output reservation'):
        run_conversion(spec,{'source':source},tmp_path/'table',max_output_bytes=100)
    assert (tmp_path/'table/records.parquet').stat().st_size<=100
    spec={'name':'retained_visual_image_jsonl','params':{},'count':2,'rows_sha256':'0'*64}
    with pytest.raises(ValueError,match='output reservation'):
        run_conversion(spec,{'source':source},tmp_path/'json',max_output_bytes=100)
    assert (tmp_path/'json/records.jsonl').stat().st_size<=100
    assert not (tmp_path/'json/media').exists()


def test_worker_subtracts_retained_input_bytes_before_bounded_conversion(tmp_path):
    source=original(tmp_path);sha=hashlib.sha256(source.read_bytes()).hexdigest();size=source.stat().st_size
    register_source(tmp_path,source,sha,size)
    dataset=Dataset(id='fixture',name='Fixture',adapter='retained_parquet_media',release='r',snapshot_id='s')
    path=tmp_path/'registry/datasets/fixture.yaml';path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    recipe={'adapter':'retained_parquet_media','snapshot_id':'s','expected_count':2,'scope':'Synthetic fixture',
        'files':[{'source_name':'original.parquet','url':'https://example.org/original.parquet','sha256':sha,
                  'bytes':size,'format':'parquet','config_key':'source'}],
        'convert':{'name':'retained_visual_parquet','params':{'mode':'realworldqa',
            'sources':[{'key':'source','native_path':'test.parquet'}]},'count':2,'rows_sha256':'0'*64}}
    path=tmp_path/'registry/recipes/fixture.yaml';path.parent.mkdir(parents=True);path.write_text(yaml.safe_dump(recipe))
    manager=PreparationManager(tmp_path);plan=manager.plan('fixture',size+1,size+100)
    assert plan['ready']
    with pytest.raises(ValueError,match='output reservation'):run(tmp_path,plan['id'],activate=False)
    converted=tmp_path/'work/prepared/fixture'/plan['id']/'sources/converted/records.parquet'
    assert converted.stat().st_size<=100
    assert not (tmp_path/'work/prepared/fixture/active.json').exists()


def test_successful_bounded_conversion_preserves_plan_id_and_normal_activation(tmp_path):
    original_path=original(tmp_path);sha=hashlib.sha256(original_path.read_bytes()).hexdigest();size=original_path.stat().st_size
    register_source(tmp_path,original_path,sha,size)
    expected=retained_visual_image_jsonl({}, {'source':original_path},tmp_path/'expected',lambda:None,max_output_bytes=10000)
    dataset=Dataset(id='fixture',name='Fixture',adapter='retained_parquet_media',release='r',snapshot_id='s',
        adapter_config={'mapping':{'id':'example_id','question':'prompt','media':'media_path'}})
    path=tmp_path/'registry/datasets/fixture.yaml';path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    recipe={'adapter':'retained_parquet_media','snapshot_id':'s','expected_count':2,'scope':'Synthetic fixture',
        'files':[{'source_name':'original.parquet','url':'https://example.org/original.parquet','sha256':sha,
                  'bytes':size,'format':'parquet','config_key':'source'}],
        'convert':{'name':'retained_visual_image_jsonl','params':{},'count':2,'rows_sha256':expected['rows_sha256']}}
    path=tmp_path/'registry/recipes/fixture.yaml';path.parent.mkdir(parents=True);path.write_text(yaml.safe_dump(recipe))
    manager=PreparationManager(tmp_path);plan=manager.plan('fixture',size+1,1_000_000)
    run(tmp_path,plan['id'])
    base=tmp_path/'work/prepared/fixture';pointer=json.loads((base/'active.json').read_text())
    assert type(pointer['version']) is str and pointer['version']==plan['id']
    receipt=json.loads((base/plan['id']/'receipt.json').read_text())
    assert type(receipt['plan_id']) is str and receipt['plan_id']==plan['id']
    assert manager.registry.active_directory('fixture')==base/plan['id']


def test_converted_source_bytes_reduce_the_preview_and_index_reservation(tmp_path):
    path=tmp_path/'original.parquet'
    pq.write_table(pa.Table.from_pylist([{'example_id':'wide','prompt':'x'*400_000,
        'image':{'bytes':image('red'),'path':'wide.png'}}]),path)
    sha=hashlib.sha256(path.read_bytes()).hexdigest();size=path.stat().st_size
    register_source(tmp_path,path,sha,size)
    expected=retained_visual_image_jsonl({}, {'source':path},tmp_path/'expected',lambda:None,max_output_bytes=1_000_000)
    dataset=Dataset(id='fixture',name='Synthetic wide conversion',adapter='retained_parquet_media',release='r',snapshot_id='s',
        adapter_config={'mapping':{'id':'example_id','question':'prompt','media':'media_path'}})
    entry=tmp_path/'registry/datasets/fixture.yaml';entry.parent.mkdir(parents=True);entry.write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    recipe={'adapter':'retained_parquet_media','snapshot_id':'s','expected_count':1,'scope':'Synthetic fixture only',
        'files':[{'source_name':'original.parquet','url':'https://example.org/original.parquet','sha256':sha,
                  'bytes':size,'format':'parquet','config_key':'source'}],
        'convert':{'name':'retained_visual_image_jsonl','params':{},'count':1,'rows_sha256':expected['rows_sha256']}}
    entry=tmp_path/'registry/recipes/fixture.yaml';entry.parent.mkdir(parents=True);entry.write_text(yaml.safe_dump(recipe))
    manager=PreparationManager(tmp_path);plan=manager.plan('fixture',size+1,1_000_000)
    assert plan['ready']
    # Conversion and preview each fit alone. Their combined output must not be
    # registered when it exceeds the one approved preparation reservation.
    with pytest.raises(ValueError,match='budget|reservation'):
        run(tmp_path,plan['id'])
    assert not (tmp_path/'work/prepared/fixture/active.json').exists()
