"""Synthetic native topology only; no corpus recordings or text used in tests."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import wave
import zipfile

import pyarrow.parquet as pq
import pytest

from dataset_atlas.converters.collections import spoken_wikipedia_sentences
from dataset_atlas.preparation.zip_tar import register_index,verified_index,prepare_sources,validate_sources
from dataset_atlas.storage.zip_tar import build_zip_tar_index


def native_fixture(root,changed_metadata=False):
    root.mkdir(parents=True,exist_ok=True);inputs={};sources={};readers={};waveform=io.BytesIO()
    with wave.open(waveform,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\x00\x00'*800)
    audio=waveform.getvalue()
    for language in ('Dutch','English','German'):
        annotation={'./fixture/info.json':b'{"article":{"fixture":true},"audio_files":["fixture.wav"]}',
            './fixture/aligned.swc':b'<article><s start="0" end="100"><n>fixture</n></s><s><n>second</n></s></article>'}
        path=root/(language+'.tar.xz')
        with tarfile.open(path,mode='w:xz') as tar:
            for name,data in annotation.items():
                info=tarfile.TarInfo(name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
        inputs[language]=path
        full=io.BytesIO()
        with tarfile.open(fileobj=full,mode='w') as tar:
            for name,data in {**annotation,'./fixture/audio.wav':audio}.items():
                if changed_metadata and language=='Dutch' and name.endswith('info.json'):data=b'{"changed":true}'
                info=tarfile.TarInfo(name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
        native=full.getvalue();parent=io.BytesIO()
        with zipfile.ZipFile(parent,mode='w',compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr(language+'.tar',native)
        with zipfile.ZipFile(io.BytesIO(parent.getvalue())) as archive:info=archive.getinfo(language+'.tar')
        spec={'url':'https://fixture.invalid/'+language+'.zip','archive_bytes':len(parent.getvalue()),'etag':'"fixture"','allowed_hosts':['fixture.invalid'],
            'member':language+'.tar','bytes':len(native),'compressed_bytes':info.compress_size,'crc32':info.CRC,'sha256':hashlib.sha256(native).hexdigest()}
        def factory(payload):
            class Reader(io.BytesIO):
                def __init__(self,*args,**kwargs):super().__init__(payload);self.bytes_fetched=0
                def read(self,size=-1):
                    data=super().read(size);self.bytes_fetched+=len(data);return data
            return Reader
        reader=factory(parent.getvalue());index=root/('index-'+language)
        build_zip_tar_index(spec,index,byte_budget=1_000_000,reader_factory=reader)
        inputs['audio_index_'+language]=index;sources[language]=spec;readers[language]=reader
    return inputs,sources,readers,audio


def test_native_audio_preserves_sentence_membership_and_complete_article_originals(tmp_path,monkeypatch):
    from dataset_atlas.adapters.spoken_wikipedia import SpokenWikipediaAdapter
    from dataset_atlas.models import Dataset
    from dataset_atlas.storage.indexed_tar import read_tar_member
    import dataset_atlas.adapters.spoken_wikipedia as module
    inputs,sources,readers,audio=native_fixture(tmp_path/'source')
    result=spoken_wikipedia_sentences({},inputs,tmp_path/'out',lambda:None)
    rows=pq.read_table(result['path']).to_pylist()
    assert len(rows)==6 and {row['language'] for row in rows}==set(sources)
    assert all(row['article_path']=='./fixture' and 'native_alignment_xml' in row for row in rows)
    assert all(row['native_sentence_attributes'] in ('{"start": "0", "end": "100"}','{}') for row in rows)
    dataset=Dataset(id='synthetic-swc',name='Synthetic audio corpus',release='fixture',snapshot_id='fixture',adapter='spoken_wikipedia',
        adapter_config={**result['adapter_config'],'path':str(result['path']),'format':'parquet','sha256':result['file_sha256'],
            'native_audio_archives':{key:str(inputs['audio_index_'+key]) for key in sources},'native_audio_sources':sources,
            'remote_cache_root':str(tmp_path/'cache'),'remote_cache_bytes':1_000_000})
    adapter=SpokenWikipediaAdapter(dataset);source=adapter.prepare(adapter.plan(10,5_000_000))
    records=list(adapter.iter_sequential(source))
    assert len({record.id for record in records})==6 and len({record.assets[0].id for record in records})==3
    def read(index,member,**kwargs):
        language=Path(index).name.removeprefix('index-')
        return read_tar_member(index,member,reader_factory=readers[language],**kwargs)
    monkeypatch.setattr(module,'read_tar_member',read)
    media_source=adapter.prepare_media(adapter.plan(3,5_000_000))
    for record in records[::2]:
        asset=record.assets[0];handle=adapter.resolve_asset(media_source,asset.uri)
        assert handle.data==audio and handle.sha256==asset.sha256 and handle.media_type=='audio/wav'
        assert asset.metadata['audio_extent'].startswith('complete native article')


def test_native_audio_conversion_rejects_changed_annotation_join(tmp_path):
    inputs,_,_,_=native_fixture(tmp_path/'source',changed_metadata=True)
    with pytest.raises(ValueError,match='article metadata differ'):
        spoken_wikipedia_sentences({},inputs,tmp_path/'bad',lambda:None)


def test_native_seek_cache_reuse_is_verified_and_requires_no_source_transfer(tmp_path):
    inputs,sources,_,_=native_fixture(tmp_path/'source');validate_sources(sources)
    for language,spec in sources.items():register_index(tmp_path,inputs['audio_index_'+language],spec)
    plan={'zip_tar_sources':sources,'native_zip_tar_index_bytes':1_000_000,'max_download_bytes':1_000_000,'expected_annotation_transfer_bytes':10000}
    result=prepare_sources(tmp_path,plan,tmp_path/'prepared',lambda **_:None,lambda:None)
    assert result['source_transfer_bytes']==0 and all(proof['reused_verified_index'] for proof in result['proofs'])
    first=Path(result['indices']['Dutch']);assert verified_index(first,sources['Dutch'])
    with (first/'members.sqlite').open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='checksum changed'):verified_index(first,sources['Dutch'])
    with pytest.raises(ValueError,match='pinned SHA-256'):validate_sources({'Dutch':{**sources['Dutch'],'sha256':None}})


def test_native_audio_container_is_fully_decoded_and_bounded(tmp_path):
    import shutil
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):pytest.skip('FFmpeg not installed')
    from dataset_atlas.storage.audio import verify_audio
    from dataset_atlas.adapters.remote_columnar import MediaLimitError
    _,_,_,audio=native_fixture(tmp_path/'source')
    result=verify_audio(audio)
    assert result['full_audio_decode_checked'] is True and result['decoded_sample_count_upper_bound']<=801
    with pytest.raises(MediaLimitError,match='duration limit'):verify_audio(audio,max_duration_seconds=0.01)
    with pytest.raises(ValueError,match='decoding failed'):verify_audio(audio[:20])


def test_audio_decoder_cancellation_reaps_a_process_after_pipe_eof():
    import sys,time
    from dataset_atlas.storage.audio import _decoded_samples
    class Cancelled(Exception):pass
    started=time.monotonic()
    def cancel():
        if time.monotonic()-started>.15:raise Cancelled()
    with pytest.raises(Cancelled):
        _decoded_samples([sys.executable,'-c','import os,time;os.close(1);os.close(2);time.sleep(10)'],
                         sample_rate=8000,channels=1,max_samples=8000,max_duration_seconds=1,timeout_seconds=20,cancel=cancel)
    assert time.monotonic()-started<2


def test_native_audio_preparation_pins_sources_index_and_playable_preview(tmp_path,monkeypatch):
    import yaml
    import dataset_atlas.adapters.spoken_wikipedia as module
    from dataset_atlas.models import Dataset
    from dataset_atlas.preparation import PreparationManager
    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry
    from dataset_atlas.storage.https import HttpsFetcher
    from dataset_atlas.storage.indexed_tar import read_tar_member
    inputs,sources,readers,audio=native_fixture(tmp_path/'native')
    converted=spoken_wikipedia_sentences({},inputs,tmp_path/'expected',lambda:None)
    for language,spec in sources.items():register_index(tmp_path,inputs['audio_index_'+language],spec)
    def fetch(self,url,*args,**kwargs):
        language=Path(url).name.removesuffix('.tar.xz');path=inputs[language];self.bytes_fetched+=path.stat().st_size;return path
    monkeypatch.setattr(HttpsFetcher,'fetch',fetch)
    def read(index,member,**kwargs):return read_tar_member(index,member,reader_factory=readers[Path(index).name],**kwargs)
    monkeypatch.setattr(module,'read_tar_member',read)
    dataset=Dataset(id='synthetic-swc',name='Synthetic preparation',adapter='spoken_wikipedia',source_url='https://fixture.invalid/source')
    directory=tmp_path/'registry/datasets';directory.mkdir(parents=True)
    (directory/'synthetic-swc.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    recipe={'adapter':'spoken_wikipedia','scope':'Synthetic exact native sentence fixture only','expected_count':6,
        'zip_tar_sources':sources,'native_zip_tar_index_bytes':1_000_000,
        'adapter_config':{'verify_remote_preview_media':True,'preview_media_modalities':['audio'],'preview_group_by':'primary_asset_then_example',
            'media_scope':'partial','remote_cache_root':str(tmp_path/'cache'),'remote_cache_bytes':1_000_000},
        'convert':{'name':'spoken_wikipedia_sentences','count':6,'rows_sha256':converted['rows_sha256']},
        'files':[{'source_name':language+'.tar.xz','config_key':language,'format':'tar.xz','url':'https://fixture.invalid/'+language+'.tar.xz',
            'bytes':inputs[language].stat().st_size,'sha256':hashlib.sha256(inputs[language].read_bytes()).hexdigest()} for language in sources]}
    recipes=tmp_path/'registry/recipes';recipes.mkdir()
    (recipes/'synthetic-swc.yaml').write_text(yaml.safe_dump(recipe))
    manager=PreparationManager(tmp_path)
    import importlib.util
    import shutil
    with monkeypatch.context() as missing:
        missing.setattr(shutil,'which',lambda _:None)
        denied=manager.plan(dataset.id,5_000_000,5_000_000)
        assert not denied['ready'] and any('FFmpeg and ffprobe before source acquisition' in message for message in denied['requirements'])
    original_find=importlib.util.find_spec
    with monkeypatch.context() as missing:
        missing.setattr(importlib.util,'find_spec',lambda name:None if name=='indexed_gzip' else original_find(name))
        denied=manager.plan(dataset.id,5_000_000,5_000_000)
        assert not denied['ready'] and any('Native ZIP/TAR seek indices require' in message for message in denied['requirements'])
    plan=manager.plan(dataset.id,5_000_000,5_000_000)
    assert plan['ready'] and plan['required_free_bytes']<75_000_000
    run(tmp_path,plan['id'])
    assert manager.status(plan['id'])['status']=='completed'
    registry=Registry(tmp_path);pack=registry.pack(dataset.id)
    assert len(pack.records)==6 and len(pack.checksums)==1
    active=registry.active_directory(dataset.id)
    assert all((active/'pack'/asset.uri).read_bytes()==audio for row in pack.records for asset in row.assets)
    receipt=json.loads((active/'receipt.json').read_text())
    assert receipt['preview_media_validation']['verified_preview_assets']==6
    assert receipt['retained_preview_original_bytes']==len(audio)
    from fastapi.testclient import TestClient
    from dataset_atlas.api import create_app
    with TestClient(create_app(tmp_path)) as client:
        exposed=client.get('/api/v1/datasets/'+dataset.id+'/pack').json()['records'][0]['assets'][0]
        response=client.get(exposed['uri'])
        assert response.content==audio and response.headers['content-type']=='audio/wav'
        partial=client.get(exposed['uri'],headers={'Range':'bytes=0-11'})
        assert partial.status_code==206 and partial.content==audio[:12]


def test_audio_limits_count_pcm_when_mp3_header_underreports_duration(tmp_path):
    import shutil
    import struct
    import subprocess
    from dataset_atlas.adapters.remote_columnar import MediaLimitError
    from dataset_atlas.storage.audio import verify_audio
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):pytest.skip('FFmpeg not installed')
    path=tmp_path/'synthetic.mp3'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
        'sine=frequency=440:duration=1:sample_rate=44100','-ac','1','-c:a','libmp3lame','-b:a','128k',str(path)],
        check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
    data=bytearray(path.read_bytes());offset=data.find(b'Info')
    if offset<0:offset=data.find(b'Xing')
    assert offset>=0 and struct.unpack_from('>I',data,offset+4)[0]&1
    struct.pack_into('>I',data,offset+8,2)
    with pytest.raises(MediaLimitError,match='actual decoded-sample'):
        verify_audio(bytes(data),max_samples=12000)
    with pytest.raises(MediaLimitError,match='duration preview limit'):
        verify_audio(bytes(data),max_duration_seconds=.5)
    result=verify_audio(bytes(data))
    assert result['decoded_sample_count']==44100 and result['decoded_duration_seconds']==1
