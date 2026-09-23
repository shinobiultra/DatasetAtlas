import hashlib
import io
import json
import zipfile

import pytest
import yaml
from PIL import Image


def test_retirement_pins_full_quality_preview_and_preserves_original_retrieval(workspace, pack, monkeypatch):
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
    pack.dataset.adapter_config = {'archive': str(source), 'archive_sha256': sha, 'repacked':str(repacked), 'repacked_sha256':repacked_sha}
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
