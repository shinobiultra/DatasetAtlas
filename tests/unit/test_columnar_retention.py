"""Synthetic native-shard retirement and cold retrieval acceptance tests."""
import hashlib
import io
import json
import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from PIL import Image

from dataset_atlas.adapters import get_adapter, resolve_dataset_asset
from dataset_atlas.adapters.core import MediaHandle
from dataset_atlas.models import Dataset, Pack
from dataset_atlas.queries.parquet import build_parquet_snapshot
from dataset_atlas.registry import Registry
from dataset_atlas.storage.columnar_retention import retire_columnar_sources, read_columnar_member


def fixture(tmp_path, monkeypatch,encoding=None):
    files=[];payloads={};expected={}
    for shard in range(2):
        rows=[]
        for row in range(3):
            picture=io.BytesIO();Image.new('RGB',(9+row,7),(shard*40,row*50,6)).save(picture,'JPEG')
            data=picture.getvalue();expected[shard*3+row]=data
            # A raw binary column absent from preview rows exercises the schema union.
            if encoding=='base64':
                import base64
                rows.append({'image':base64.b64encode(data).decode(),'label':row})
            else:rows.append({'image':{'path':f'fixture-{row}.jpg','bytes':data},'other':None if row==0 else data,'label':row})
        path=tmp_path/'work/sources'/f'{shard}.parquet';path.parent.mkdir(parents=True,exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows),path,row_group_size=2)
        payloads[str(shard)+'.parquet']=path.read_bytes()
        files.append({'source_name':str(shard)+'.parquet','path':str(path),'format':'parquet','bytes':path.stat().st_size,
                      'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                      'url':'https://huggingface.co/datasets/fixture/fixture/resolve/'+'a'*40+'/'+path.name})
    dataset=Dataset(id='fixture',name='Synthetic native columnar',adapter='columnar',release='r1',snapshot_id='s1',
                    adapter_config={'files':files,**({'media_encoding':'base64','media_columns':['image']} if encoding else {})})
    directory=tmp_path/'registry/datasets';directory.mkdir(parents=True)
    (directory/'fixture.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    adapter=get_adapter(dataset);source=adapter.prepare(adapter.plan(100,1_000_000))
    records=adapter.iter_records(source).records
    pack=Pack(dataset=dataset,records=[records[0],records[2],records[3]],fields=[])
    directory=tmp_path/'work/packs/fixture';directory.mkdir(parents=True)
    (directory/'pack.json').write_text(pack.model_dump_json())
    snapshots=tmp_path/'work/snapshots';snapshots.mkdir()
    build_parquet_snapshot(records,[],snapshots/'fixture',root=snapshots,dataset_id='fixture',release_id='r1',snapshot_id='s1',
                           expected_count=6,population_scope='complete')
    monkeypatch.setattr('dataset_atlas.storage.ranges.range_fingerprint',lambda *a,**k:'"fixture"')
    monkeypatch.setattr('dataset_atlas.storage.ranges.HttpsRangeReader._fetch',lambda self,start,end:payloads[self.url.rsplit('/',1)[1]][start:end+1])
    return dataset,files,records,expected


def options():
    return dict(max_source_bytes=1_000_000,max_preview_bytes=1_000_000,max_transfer_bytes=1_000_000,max_index_bytes=1_000_000)


def test_retirement_preserves_preview_and_complete_native_identities(tmp_path, monkeypatch):
    dataset,files,records,expected=fixture(tmp_path,monkeypatch)
    source=tmp_path/'work/source-objects'/files[0]['sha256'];source.parent.mkdir()
    os.link(files[0]['path'],source)
    snapshot=tmp_path/'work/snapshots/fixture/records.parquet'
    before=hashlib.sha256(snapshot.read_bytes()).hexdigest()
    proof=retire_columnar_sources(tmp_path,'fixture',execute=True,**options())
    assert proof['executed'] and proof['status']=='executed' and proof['freed_source_allocated_bytes']>0
    assert len(proof['source_paths_retired'])==3
    assert all(not Path(f['path']).exists() for f in files) and not source.exists()
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==before
    from dataset_atlas.storage.compact import read_compact
    assert records[2].assets[0].id==records[2].assets[1].id
    for asset in records[2].assets:
        assert read_compact(tmp_path,'fixture','s1',asset.uri,10000)[0]==expected[2]
    dataset=Registry(tmp_path).dataset('fixture')
    for row in (0,1,5):
        original=resolve_dataset_asset(dataset,records[row].assets[0].uri,workspace_root=tmp_path)
        assert original.data==expected[row] and original.media_type=='image/jpeg'
    # Another binary column omitted by both preview records is still available.
    assert resolve_dataset_asset(dataset,records[5].assets[1].uri,workspace_root=tmp_path).data==expected[5]
    index=tmp_path/'work/original-access'/proof['versions'][0]['index']/'members.sqlite'
    with index.open('ab') as stream:stream.write(b'changed index')
    with pytest.raises(ValueError,match='index checksum changed'):
        resolve_dataset_asset(dataset,records[1].assets[0].uri,workspace_root=tmp_path)


def test_retirement_refuses_shared_dependencies_and_failed_cold_identity(tmp_path,monkeypatch):
    dataset,files,records,expected=fixture(tmp_path,monkeypatch)
    shared=dataset.model_copy(update={'id':'shared','name':'Shared native source'})
    path=tmp_path/'registry/datasets/shared.yaml';path.write_text(yaml.safe_dump(shared.model_dump(mode='json')))
    with pytest.raises(ValueError,match='required by another retained dataset'):
        retire_columnar_sources(tmp_path,'fixture',execute=True,**options())
    assert all(Path(f['path']).exists() for f in files)
    path.unlink()
    monkeypatch.setattr('dataset_atlas.adapters.remote_columnar.RemoteColumnarAdapter.resolve_original_asset',
                        lambda *a,**k:MediaHandle(b'wrong','image/jpeg','0'*64,'fixture'))
    with pytest.raises(ValueError,match='differs from the measured native original'):
        retire_columnar_sources(tmp_path,'fixture',execute=True,**options())
    assert all(Path(f['path']).exists() for f in files)


def test_native_base64_parquet_retirement_preserves_exact_originals(tmp_path,monkeypatch):
    dataset,files,records,expected=fixture(tmp_path,monkeypatch,encoding='base64')
    snapshot=tmp_path/'work/snapshots/fixture/records.parquet';before=hashlib.sha256(snapshot.read_bytes()).hexdigest()
    proof=retire_columnar_sources(tmp_path,'fixture',execute=True,**options())
    assert proof['executed'] and proof['freed_source_allocated_bytes']>0
    assert all(not Path(f['path']).exists() for f in files)
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==before
    dataset=Registry(tmp_path).dataset('fixture')
    for row in (0,1,5):
        handle=resolve_dataset_asset(dataset,records[row].assets[0].uri,workspace_root=tmp_path)
        assert handle.data==expected[row] and handle.sha256==hashlib.sha256(expected[row]).hexdigest()


@pytest.mark.parametrize('prefix',['./','work/../',''])
def test_retirement_normalizes_relative_shared_dependencies(tmp_path,monkeypatch,prefix):
    dataset,files,_,_=fixture(tmp_path,monkeypatch,encoding='base64')
    shared=dataset.model_copy(deep=True,update={'id':'shared','name':'Shared native source'})
    for entry in shared.adapter_config['files']:
        entry['path']=prefix+Path(entry['path']).relative_to(tmp_path).as_posix()
    (tmp_path/'registry/datasets/shared.yaml').write_text(yaml.safe_dump(shared.model_dump(mode='json')))
    with pytest.raises(ValueError,match='required by another retained dataset'):
        retire_columnar_sources(tmp_path,'fixture',execute=True,**options())
    assert all(Path(f['path']).is_file() for f in files)


def test_retirement_plan_and_budget_failure_never_remove_native_files(tmp_path,monkeypatch):
    dataset,files,_,_=fixture(tmp_path,monkeypatch)
    proof=retire_columnar_sources(tmp_path,'fixture',**options())
    assert not proof['executed'] and not proof['source_paths_retired']
    assert all(Path(f['path']).exists() for f in files)
    with pytest.raises(ValueError,match='output budget'):
        retire_columnar_sources(tmp_path,'fixture',execute=True,**(options()|{'max_index_bytes':1}))
    assert all(Path(f['path']).exists() for f in files)


def test_original_byte_route_does_not_expand_rasters(tmp_path,monkeypatch):
    dataset,_,records,expected=fixture(tmp_path,monkeypatch)
    with monkeypatch.context() as guard:
        guard.setattr("dataset_atlas.adapters.embedded_parquet.Image.open",lambda *a,**k:(_ for _ in ()).throw(AssertionError("No original raster expansion")))
        assert resolve_dataset_asset(dataset,records[1].assets[0].uri,workspace_root=tmp_path).data==expected[1]
    proof=retire_columnar_sources(tmp_path,'fixture',**options())
    index=tmp_path/'work/original-access'/proof['versions'][0]['index']
    def reject_raster_decode(*a,**k):raise AssertionError('Original retrieval must not expand pixels')
    monkeypatch.setattr('dataset_atlas.adapters.remote_columnar.Image.open',reject_raster_decode)
    data,receipt=read_columnar_member(index,records[1].assets[0].uri,max_bytes=10000,transfer_bytes=100000)
    assert data==expected[1] and receipt['media_type']=='image/jpeg'
    with pytest.raises(ValueError,match='byte budget'):
        read_columnar_member(index,records[1].assets[0].uri,max_bytes=1,transfer_bytes=100000)


def test_retired_preview_revalidation_preserves_snapshot_and_prior_pack(tmp_path,monkeypatch):
    import shutil
    from dataset_atlas.storage.columnar_retention import verify_retired_preview
    dataset,_,_,_=fixture(tmp_path,monkeypatch)
    retire_columnar_sources(tmp_path,'fixture',execute=True,**options())
    active=tmp_path/'work/prepared/fixture/version';active.mkdir(parents=True)
    shutil.copytree(tmp_path/'work/packs/fixture',active/'pack')
    shutil.copytree(tmp_path/'work/snapshots/fixture',active/'snapshot')
    (active/'dataset.json').write_text(dataset.model_dump_json())
    (active/'receipt.json').write_text(json.dumps({'snapshot_id':'s1','record_count':6}))
    (active.parent/'active.json').write_text(json.dumps({'version':'version'}))
    before=(active/'pack/pack.json').read_bytes()
    plan=verify_retired_preview(tmp_path,'fixture',max_transfer_bytes=1000000,max_preview_bytes=1000000)
    assert not plan['executed'] and plan['preview_records']==6 and (active/'pack/pack.json').read_bytes()==before
    with pytest.raises(ValueError,match='byte budget'):
        verify_retired_preview(tmp_path,'fixture',max_transfer_bytes=1000000,max_preview_bytes=1,execute=True)
    assert (active/'pack/pack.json').read_bytes()==before
    result=verify_retired_preview(tmp_path,'fixture',max_transfer_bytes=1000000,max_preview_bytes=1000000,execute=True)
    assert result['executed'] and result['native_snapshot_changed'] is False
    assert (tmp_path/result['prior_preview_audit']/'previous-pack.json').read_bytes()==before
    pack=Registry(tmp_path).pack('fixture')
    assert len(pack.records)==6 and pack.dataset.coverage.preview_count==6
    assert pack.sampling['method']=='sha256_bottom_k_primary_asset_verified_media'
    from dataset_atlas.storage.compact import read_compact
    for record in pack.records:
        for asset in record.assets:
            if asset.uri:assert read_compact(tmp_path,'fixture','s1',asset.uri,10000)[2]['protected_preview']
