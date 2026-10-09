import hashlib,io,json
from PIL import Image
import numpy as np
import pytest
from test_corruptions import make
from test_hash_ranges import transport
from dataset_atlas.storage.cifar_ranges import build_cifar_index,read_cifar_row
from dataset_atlas.adapters.corruptions import CIFARCorruptionsAdapter


def test_remote_cifar_rows_preserve_native_pixels_after_original_removal(tmp_path,monkeypatch):
    adapter=make(tmp_path);source=adapter._path();payload=source.read_bytes();index=tmp_path/'index'
    receipt=build_cifar_index(source,index,source_sha256=hashlib.sha256(payload).hexdigest(),url='https://example.org/native',
             allowed_hosts=['example.org'],config=adapter.config)
    assert receipt['records']==12
    prep=adapter.prepare(adapter.plan(1,1000000));before=adapter.resolve_asset(prep,'blur/5.png').data
    source.unlink();transport(monkeypatch,payload)
    data,proof=read_cifar_row(index,'blur/5.png');assert data==before
    with Image.open(io.BytesIO(data)) as image:assert np.array_equal(np.asarray(image),np.full((32,32,3),50,dtype=np.uint8))
    assert proof['fingerprint_type']=='sha256-blocks' and proof['native_rgb_sha256']==hashlib.sha256(bytes([50])*3072).hexdigest()
    for ref in ['blur/6.png','../labels.npy','noise/-1.png','unknown/0.png']:
        with pytest.raises(ValueError):read_cifar_row(index,ref)
    with pytest.raises(ValueError,match='output bound'):read_cifar_row(index,'blur/0.png',max_bytes=1)


def test_corrupted_remote_block_or_row_bounds_are_refused(tmp_path,monkeypatch):
    adapter=make(tmp_path);source=adapter._path();payload=source.read_bytes();index=tmp_path/'index'
    build_cifar_index(source,index,source_sha256=hashlib.sha256(payload).hexdigest(),url='https://example.org/native',allowed_hosts=['example.org'],config=adapter.config)
    transport(monkeypatch,payload,alter=True)
    with pytest.raises(ValueError,match='SHA-256'):read_cifar_row(index,'noise/0.png')
    r=json.loads((index/'receipt.json').read_text());r['arrays']['noise']['offset']=len(payload);(index/'receipt.json').write_text(json.dumps(r))
    with pytest.raises(ValueError,match='offset'):read_cifar_row(index,'noise/0.png')


@pytest.mark.parametrize('scenario',['retire','shared','fractional','bool-label','unhashed-old','missing-snapshot','writer','external-index'])
def test_retirement_preserves_canonical_and_preview_pixels_and_refuses_shared_source(tmp_path,monkeypatch,scenario):
    import yaml
    from dataset_atlas.models import Pack
    from dataset_atlas.queries.parquet import build_parquet_snapshot
    from dataset_atlas.storage.cifar_ranges import retire_cifar_archive
    from dataset_atlas.storage.indexed_tar import read_original_route
    from dataset_atlas.storage.compact import read_compact
    adapter=make(tmp_path);source_dir=tmp_path/'work/sources';source_dir.mkdir(parents=True)
    original=adapter._path();source=source_dir/'native.tar';original.rename(source);payload=source.read_bytes()
    dataset=adapter.dataset.model_copy(deep=True);dataset.id='cifar-10-c';dataset.adapter_config['path']=str(source)
    dataset.adapter_config['source_files']=[{'path':str(source),'sha256':hashlib.sha256(payload).hexdigest(),'url':'https://zenodo.org/native.tar'}]
    adapter=CIFARCorruptionsAdapter(dataset)
    prepared=adapter.prepare(adapter.plan(12,1_000_000));rows=adapter.iter_records(prepared,limit=12).records
    if scenario=='fractional':
        for row in rows:row.source['severity']+=0.5
    if scenario=='bool-label':rows[0].source['label']=False
    pack=Pack(dataset=dataset,records=[rows[0]],fields=[])
    directory=tmp_path/'registry/datasets';directory.mkdir(parents=True)
    (directory/'cifar-10-c.yaml').write_text(yaml.safe_dump(dataset.model_dump(mode='json')))
    packs=tmp_path/'work/packs/cifar-10-c';packs.mkdir(parents=True);(packs/'pack.json').write_text(pack.model_dump_json())
    snapshots=tmp_path/'work/snapshots';snapshots.mkdir()
    build_parquet_snapshot(rows,[],snapshots/'cifar-10-c',root=snapshots,dataset_id=dataset.id,release_id=dataset.release,
                           snapshot_id=dataset.snapshot_id,expected_count=12,population_scope='complete')
    transport(monkeypatch,payload)
    if scenario=='external-index':
        external=tmp_path/'external';build_cifar_index(source,external,source_sha256=hashlib.sha256(payload).hexdigest(),
                    url='https://zenodo.org/native.tar',allowed_hosts=['zenodo.org'],config=dataset.adapter_config)
        base=tmp_path/'work/original-access';base.mkdir(parents=True)
        (base/('cifar-c-'+hashlib.sha256(payload).hexdigest())).symlink_to(external,target_is_directory=True)
        with pytest.raises(ValueError,match='outside configured root'):retire_cifar_archive(tmp_path,dataset.id,execute=True)
        assert source.exists()
    elif scenario in ['unhashed-old','missing-snapshot']:
        old=dataset.model_copy(deep=True);old.snapshot_id='old'
        if scenario=='unhashed-old':old.adapter_config={'path':str(source)}
        old_dir=tmp_path/'work/prepared/cifar-10-c/old';(old_dir/'pack').mkdir(parents=True)
        (old_dir/'dataset.json').write_text(old.model_dump_json())
        (old_dir/'pack/pack.json').write_text(Pack(dataset=old,records=[rows[0]],fields=[]).model_dump_json())
        with pytest.raises(ValueError,match='lacks verified source identity|no complete canonical snapshot'):retire_cifar_archive(tmp_path,dataset.id,execute=True)
        assert source.exists()
    elif scenario=='writer':
        from dataset_atlas.preparation.slots import try_writer_slot
        from dataset_atlas.preparation import PreparationManager
        with try_writer_slot(PreparationManager(tmp_path).directory,dataset.id):
            with pytest.raises(RuntimeError,match='preparation owns'):retire_cifar_archive(tmp_path,dataset.id,execute=True)
        assert source.exists()
    elif scenario in ['fractional','bool-label']:
        with pytest.raises(ValueError,match='native integer'):retire_cifar_archive(tmp_path,dataset.id,execute=True)
        assert source.exists()
    elif scenario=='shared':
        other=dataset.model_copy(deep=True);other.id='other';(directory/'other.yaml').write_text(yaml.safe_dump(other.model_dump(mode='json')))
        with pytest.raises(ValueError,match='another retained dataset dependency'):retire_cifar_archive(tmp_path,dataset.id,execute=True)
        assert source.exists()
    else:
        receipt=retire_cifar_archive(tmp_path,dataset.id,execute=True)
        assert receipt['canonical_records_checked']==12 and receipt['protected_preview_records_checked']==1
        assert receipt['status']=='executed' and not source.exists()
        assert read_compact(tmp_path,dataset.id,dataset.snapshot_id,'blur/0.png',1_000_000)[2]['protected_preview']
        data,_=read_original_route(tmp_path,dataset.id,dataset.snapshot_id,'noise/5.png',1_000_000)
        with Image.open(io.BytesIO(data)) as image:assert np.array_equal(np.asarray(image),np.full((32,32,3),50,dtype=np.uint8))
