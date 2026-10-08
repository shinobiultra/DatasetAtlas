import hashlib
import io
import json
import zipfile
import tarfile

import pytest
import yaml
from PIL import Image


@pytest.mark.parametrize('defect',['wrong_original','missing_source_checksum','changed_index_derivative'])
def test_independent_route_cannot_replace_unsigned_native_bytes(workspace,pack,defect):
    from dataset_atlas.storage.indexed_tar import build_tar_index,route_path
    from dataset_atlas.storage.retention import _independent_route_checker,_require_independent_excluded_asset
    from dataset_atlas.adapters.core import _safe_relative
    sources=workspace/'work/sources';sources.mkdir();source=sources/'other.tar'
    original=io.BytesIO();Image.new('RGB',(5,4),'blue').save(original,'PNG');expected_sha=hashlib.sha256(original.getvalue()).hexdigest()
    wrong=io.BytesIO();Image.new('RGB',(5,4),'red').save(wrong,'PNG');data=wrong.getvalue()
    with tarfile.open(source,'w') as archive:
        member=tarfile.TarInfo('native.png');member.size=len(data);archive.addfile(member,io.BytesIO(data))
    sha=hashlib.sha256(source.read_bytes()).hexdigest();index=workspace/'work/original-access/other'
    build_tar_index(source,index,source_sha256=sha,remote={'url':'https://example.org/other.tar','bytes':source.stat().st_size,'etag':'"other"','allowed_hosts':['example.org']},max_uncompressed_bytes=1000000)
    if defect=='missing_source_checksum':
        path=index/'receipt.json';proof=json.loads(path.read_text());proof.pop('source_sha256');path.write_text(json.dumps(proof))
    if defect=='changed_index_derivative':
        with (index/'members.sqlite').open('ab') as stream:stream.write(b'changed')
    route=route_path(workspace,'fixture','s1');route.parent.mkdir(parents=True)
    route.write_text(json.dumps({'dataset_id':'fixture','snapshot_id':'s1','archives':[{'index':'other','asset_prefix':'','member_prefix':''}]}))
    checker=_independent_route_checker(workspace,pack.dataset,'0'*64)
    with pytest.raises(ValueError):
        _require_independent_excluded_asset({'uri':_safe_relative('native.png')},{expected_sha},lambda ref:expected_sha if ref=='native.png' else None,checker)
    assert source.is_file()


@pytest.mark.parametrize('native_prefixes',[True,False])
@pytest.mark.parametrize('operation',['native','repacked'])
def test_partial_prefix_cannot_retire_uncovered_native_asset(workspace,pack,monkeypatch,native_prefixes,operation):
    from dataset_atlas.models import Asset,Record
    from dataset_atlas.queries.parquet import build_parquet_snapshot
    from dataset_atlas.storage.indexed_tar import build_tar_index,route_path
    from dataset_atlas.storage.retention import retire_image_archive,retire_repacked_archive
    sources=workspace/'work/sources';sources.mkdir()
    source=sources/'native.tar';payloads={}
    for ordinal,color in enumerate(['blue','red']):
        out=io.BytesIO();Image.new('RGB',(5,4),color).save(out,'PNG')
        name=f'{["first","second"][ordinal]}/{ordinal}.png' if native_prefixes else f'{ordinal}.png'
        payloads[name]=out.getvalue()
    with tarfile.open(source,'w') as archive:
        for name,data in payloads.items():
            info=tarfile.TarInfo(name);info.size=len(data);archive.addfile(info,io.BytesIO(data))
    payload=source.read_bytes();sha=hashlib.sha256(payload).hexdigest()
    pack.dataset.adapter_config={'archive':str(source),'archive_sha256':sha}
    assets=[Asset(id=f'a-{i}',dataset_id='fixture',release_id='r1',modality='image',
                  uri=f'{["first","second"][i]}/{i}.png',
                  sha256=hashlib.sha256(data).hexdigest() if not native_prefixes else None)
            for i,data in enumerate(payloads.values())]
    row=Record(id='item',dataset_id='fixture',release_id='r1',snapshot_id='s1',assets=assets,asset_ids=[a.id for a in assets])
    pack.records=[row];pack.fields=[]
    (workspace/'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    snapshots=workspace/'work/snapshots';snapshots.mkdir()
    build_parquet_snapshot([row],[],snapshots/'fixture',root=snapshots,dataset_id='fixture',release_id='r1',snapshot_id='s1',expected_count=1,population_scope='complete')
    index=workspace/'work/original-access/native'
    build_tar_index(source,index,source_sha256=sha,remote={'url':'https://example.org/native.tar','bytes':len(payload),'etag':'"pinned"','allowed_hosts':['example.org']},max_uncompressed_bytes=1000000)
    class Ranges(io.BytesIO):
        def __init__(self,url,**kwargs):super().__init__(payload);self.bytes_fetched=0
        def read(self,size=-1):
            value=super().read(size);self.bytes_fetched+=len(value);return value
    monkeypatch.setattr('dataset_atlas.storage.ranges.HttpsRangeReader',Ranges)
    mapping={'asset_prefix':'first/','member_prefix':'first/' if native_prefixes else ''}
    if operation=='repacked':
        repacked=sources/'repacked.zip'
        with zipfile.ZipFile(repacked,'w') as archive:
            for name,data in payloads.items():archive.writestr(name,data)
        repacked_sha=hashlib.sha256(repacked.read_bytes()).hexdigest()
        pack.dataset.adapter_config.update(repacked=str(repacked),repacked_sha256=repacked_sha)
        route=route_path(workspace,'fixture','s1');route.parent.mkdir(parents=True,exist_ok=True)
        route.write_text(json.dumps({'dataset_id':'fixture','snapshot_id':'s1','archives':[{'index':'native',**mapping}]}))
    (workspace/'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(pack.dataset.model_dump(mode='json')))
    with pytest.raises(ValueError,match='Excluded media'):
        if operation=='native':retire_image_archive(workspace,'fixture','native',source,mappings=[mapping],execute=True)
        else:retire_repacked_archive(workspace,'native',repacked,source_sha256=repacked_sha,max_decoded_bytes=1000000,execute=True)
    assert source.is_file()
    if operation=='repacked':assert repacked.is_file()
    assert not (workspace/'work/original-access/retirements/fixture-native.json').exists()


@pytest.mark.parametrize('shared_path', ['absolute', './work/sources/original.zip', 'work/sources/../sources/original.zip'])
def test_retirement_pins_full_quality_preview_and_preserves_original_retrieval(workspace, pack, monkeypatch, shared_path):
    from dataset_atlas.models import Asset, Record
    from dataset_atlas.registry import Registry
    from dataset_atlas.queries.parquet import build_parquet_snapshot
    from dataset_atlas.storage.indexed_zip import build_zip_index
    from dataset_atlas.storage.retention import retire_image_archive
    from dataset_atlas.adapters import resolve_dataset_asset
    from dataset_atlas.storage.compact import read_compact
    sources = workspace/'work/sources'; sources.mkdir()
    source = sources/'original.zip'; originals = {}
    with zipfile.ZipFile(source, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for i in range(3):
            out = io.BytesIO(); Image.new('RGB', (30 + i, 17), ('red', 'green', 'blue')[i]).save(out, 'PNG')
            originals[f'images/{i}.png'] = out.getvalue(); archive.writestr(f'Release/images/{i}.png', out.getvalue())
    payload = source.read_bytes(); sha = hashlib.sha256(payload).hexdigest()
    repacked = sources/'repacked.zip'
    with zipfile.ZipFile(repacked,'w') as archive:
        for name,data in originals.items():archive.writestr('Release/'+name,data)
    repacked_sha=hashlib.sha256(repacked.read_bytes()).hexdigest()
    pack.dataset.adapter_config = {'archive': str(source), 'archive_sha256': sha, 'repacked':str(repacked), 'repacked_sha256':repacked_sha,
                                  'description':'Synthetic ordinary metadata '+('x'*400),
                                  'slash_metadata':'/'.join(['a'*100]*50),
                                  'unknown_user_metadata':'~atlas_nonexistent_review_user'}
    (workspace/'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(pack.dataset.model_dump(mode='json')))
    rows = []
    for i, ref in enumerate(originals):
        asset = Asset(id=f'image-{i}', dataset_id='fixture', release_id='r1', modality='image', uri=ref)
        rows.append(Record(id=f'item-{i}', dataset_id='fixture', release_id='r1', snapshot_id='s1', assets=[asset], asset_ids=[asset.id]))
    pack.records = [rows[0].model_copy(deep=True)]; pack.records[0].assets[0].uri = 'media/images/0.png'; pack.fields = []
    (workspace/'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    snapshots = workspace/'work/snapshots'; snapshots.mkdir()
    build_parquet_snapshot(rows, [], snapshots/'fixture', root=snapshots, dataset_id='fixture', release_id='r1', snapshot_id='s1', expected_count=3, population_scope='complete')
    index = workspace/'work/original-access/native'
    build_zip_index(source, index, source_sha256=sha, remote={'url':'https://example.org/native.zip','bytes':len(payload),'etag':'"pinned"','allowed_hosts':['example.org']}, max_input_bytes=1_000_000)
    class Ranges(io.BytesIO):
        def __init__(self, url, **kwargs): super().__init__(payload); self.bytes_fetched=0
        def read(self, size=-1):
            data=super().read(size);self.bytes_fetched+=len(data);return data
    monkeypatch.setattr('dataset_atlas.storage.ranges.HttpsRangeReader', Ranges)
    kwargs = dict(mappings=[{'asset_prefix':'', 'member_prefix':'Release/'}, {'asset_prefix':'media/', 'member_prefix':'Release/'}])
    plan = retire_image_archive(workspace, 'fixture', 'native', source, **kwargs)
    assert plan['status'] == 'verified_plan' and source.is_file()
    shared = pack.dataset.model_copy(update={'id':'shared', 'name':'Shared source', 'snapshot_id':'s2'})
    shared.adapter_config = dict(shared.adapter_config)
    shared.adapter_config['archive'] = str(source) if shared_path == 'absolute' else shared_path
    (workspace/'registry/datasets/shared.yaml').write_text(yaml.safe_dump(shared.model_dump(mode='json')))
    with pytest.raises(ValueError, match='required by retained dataset'):
        retire_image_archive(workspace, 'fixture', 'native', source, execute=True, **kwargs)
    assert source.is_file()
    shared_rows = [row.model_copy(deep=True) for row in rows]
    for i, row in enumerate(shared_rows):
        row.id = f'shared-item-{i}'; row.dataset_id = 'shared'; row.snapshot_id = 's2'
        row.assets[0].dataset_id = 'shared'; row.assets[0].id = f'shared-image-{i}'; row.asset_ids = [row.assets[0].id]
    from dataset_atlas.models import Pack
    other_pack = workspace/'work/packs/shared'; other_pack.mkdir()
    (other_pack/'pack.json').write_text(Pack(dataset=shared, records=[shared_rows[-1]], fields=[]).model_dump_json())
    build_parquet_snapshot(shared_rows, [], snapshots/'shared', root=snapshots, dataset_id='shared', release_id='r1', snapshot_id='s2', expected_count=3, population_scope='complete')
    receipt = retire_image_archive(workspace, 'fixture', 'native', source, linked_datasets=['shared'], execute=True, **kwargs)
    assert receipt['status'] == 'executed' and not source.exists()
    assert receipt['retained_snapshots'] == 2 and receipt['linked_dataset_ids'] == ['shared']
    assert receipt['freed_unique_file_bytes'] == len(payload)
    assert read_compact(workspace, 'fixture', 's1', 'media/images/0.png', 100000)[0] == originals['images/0.png']
    assert read_compact(workspace, 'shared', 's2', 'images/2.png', 100000)[0] == originals['images/2.png']
    dataset = Registry(workspace).dataset('fixture')
    for ref, data in originals.items():
        assert resolve_dataset_asset(dataset, ref, workspace_root=workspace).data == data
    assert all(path.is_file() for path in [snapshots/'fixture/records.parquet', index/'members.sqlite'])

    from dataset_atlas.storage.retention import retire_repacked_archive
    from dataset_atlas.storage.indexed_tar import route_path
    options=dict(source_sha256=repacked_sha,max_decoded_bytes=1_000_000)
    with pytest.raises(ValueError,match='checksum changed'):
        retire_repacked_archive(workspace,'native',repacked,source_sha256='0'*64,max_decoded_bytes=1_000_000)
    shared_route=route_path(workspace,'shared','s2');saved=shared_route.read_bytes();shared_route.unlink()
    with pytest.raises(ValueError,match='native routes'):
        retire_repacked_archive(workspace,'native',repacked,execute=True,**options)
    assert repacked.is_file()
    shared_route.write_bytes(saved)
    proof=retire_repacked_archive(workspace,'native',repacked,execute=True,**options)
    assert proof['status']=='executed' and not repacked.exists()
    assert proof['all_native_members_checked']==3 and proof['image_references_checked']==6
    for ref,data in originals.items():assert resolve_dataset_asset(dataset,ref,workspace_root=workspace).data==data


def test_scoped_plain_tar_retirement_preserves_other_archive_routes(workspace, pack, monkeypatch):
    from dataset_atlas.models import Asset, Record
    from dataset_atlas.queries.parquet import build_parquet_snapshot
    from dataset_atlas.storage.indexed_tar import build_tar_index, route_path
    from dataset_atlas.storage.retention import retire_image_archive, retire_repacked_archive
    from dataset_atlas.storage.compact import read_compact
    sources=workspace/'work/sources'; sources.mkdir()
    source=sources/'native.tar.gz'; repacked=sources/'repacked.zip'
    image=io.BytesIO(); Image.new('RGB',(9,11),'blue').save(image,'PNG'); data=image.getvalue()
    with tarfile.open(source,'w') as archive:
        member=tarfile.TarInfo('0.png'); member.size=len(data); archive.addfile(member,io.BytesIO(data))
    with zipfile.ZipFile(repacked,'w') as archive: archive.writestr('0.png',data)
    payload=source.read_bytes(); sha=hashlib.sha256(payload).hexdigest()
    repacked_sha=hashlib.sha256(repacked.read_bytes()).hexdigest()
    pack.dataset.adapter_config={'archive':str(source),'archive_sha256':sha,'repacked':str(repacked),'repacked_sha256':repacked_sha}
    (workspace/'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(pack.dataset.model_dump(mode='json')))
    assets=[Asset(id='a',dataset_id='fixture',release_id='r1',modality='image',uri='first/0.png',sha256=hashlib.sha256(data).hexdigest()),
            Asset(id='b',dataset_id='fixture',release_id='r1',modality='image',uri='second/0.png',sha256=hashlib.sha256(data).hexdigest())]
    row=Record(id='item',dataset_id='fixture',release_id='r1',snapshot_id='s1',assets=assets,asset_ids=['a','b'])
    pack.records=[row]; pack.fields=[]
    (workspace/'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    snapshots=workspace/'work/snapshots'; snapshots.mkdir()
    build_parquet_snapshot([row],[],snapshots/'fixture',root=snapshots,dataset_id='fixture',release_id='r1',snapshot_id='s1',expected_count=1,population_scope='complete')
    index=workspace/'work/original-access/first'
    build_tar_index(source,index,source_sha256=sha,remote={'url':'https://example.org/native.tar.gz','bytes':len(payload),'etag':'"pinned"','allowed_hosts':['example.org']},max_uncompressed_bytes=1000000)
    # The other source really exists and has a independently verified index,
    # even though this particular image's bytes overlap the first archive.
    second=sources/'second.tar'
    with tarfile.open(second,'w') as archive:
        member=tarfile.TarInfo('0.png');member.size=len(data);archive.addfile(member,io.BytesIO(data))
        extra=b'Independent native source';member=tarfile.TarInfo('source.txt');member.size=len(extra);archive.addfile(member,io.BytesIO(extra))
    second_sha=hashlib.sha256(second.read_bytes()).hexdigest()
    build_tar_index(second,workspace/'work/original-access/second',source_sha256=second_sha,
        remote={'url':'https://example.org/second.tar','bytes':second.stat().st_size,'etag':'"independent"','allowed_hosts':['example.org']},max_uncompressed_bytes=1000000)
    route=route_path(workspace,'fixture','s1'); route.parent.mkdir(parents=True,exist_ok=True)
    other={'index':'second','asset_prefix':'second/','member_prefix':''}
    route.write_text(json.dumps({'dataset_id':'fixture','snapshot_id':'s1','archives':[other]}))
    class Ranges(io.BytesIO):
        def __init__(self,url,**kwargs):super().__init__(payload);self.bytes_fetched=0
        def read(self,size=-1):
            value=super().read(size);self.bytes_fetched+=len(value);return value
    monkeypatch.setattr('dataset_atlas.storage.ranges.HttpsRangeReader',Ranges)
    mappings=[{'asset_prefix':'first/','member_prefix':''}]
    with pytest.raises(ValueError,match='Excluded media|no media'):
        retire_image_archive(workspace,'fixture','first',source,mappings=[{'asset_prefix':'missing/'}],execute=True)
    assert source.exists()
    proof=retire_image_archive(workspace,'fixture','first',source,mappings=mappings,execute=True)
    assert proof['media_references_checked']==1 and proof['preview_asset_memberships']==1
    assert other in json.loads(route.read_text())['archives']
    assert read_compact(workspace,'fixture','s1','first/0.png',100000)[0]==data
    assert read_compact(workspace,'fixture','s1','second/0.png',100000) is None
    proof=retire_repacked_archive(workspace,'first',repacked,source_sha256=repacked_sha,max_decoded_bytes=1000000,execute=True)
    assert not repacked.exists() and proof['image_references_checked']==1
