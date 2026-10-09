"""Processors read paths: a preview original pinned in the compact store must reach them as exact, content-addressed local bytes."""
import hashlib
import io
import os
from pathlib import Path
import pytest

from PIL import Image

from dataset_atlas.adapters.core import MediaHandle
from dataset_atlas.api import create_app
from dataset_atlas.models import Asset, Record, Selection
from dataset_atlas.queries.parquet import build_parquet_snapshot
from dataset_atlas.storage.compact import pin_preview_originals


def png_bytes():
    stream = io.BytesIO()
    Image.new('RGB', (24, 18), (5, 90, 200)).save(stream, format='PNG')
    return stream.getvalue()


@pytest.mark.parametrize('cache_defect',['none','corrupt','symlink','fifo'])
def test_a_pinned_remote_preview_original_is_handed_to_processors_as_a_local_file(workspace, pack, monkeypatch,cache_defect):
    original = png_bytes()
    ref = 'file/images/native/one.png'
    asset = Asset(id='remote-one', dataset_id='fixture', release_id='r1', modality='image', uri=ref, sha256=None,
                  metadata={'representation': 'original source file'})
    row = Record(id='remote-record', dataset_id='fixture', release_id='r1', snapshot_id='s1', assets=[asset], asset_ids=[asset.id])
    pack.records = [row]
    pack.fields = []
    (workspace / 'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    snapshots = workspace / 'work/snapshots'
    snapshots.mkdir()
    build_parquet_snapshot([row], [], snapshots / 'fixture', root=snapshots, dataset_id='fixture', release_id='r1', snapshot_id='s1',
                           expected_count=1, population_scope='complete')
    monkeypatch.setattr('dataset_atlas.adapters.resolve_dataset_asset',
                        lambda _d, reference, **_: MediaHandle(original, 'image/png', hashlib.sha256(original).hexdigest(), reference))
    assert pin_preview_originals(workspace, 'fixture', max_input_bytes=100_000, max_output_bytes=100_000)['preview_image_assets_pinned'] == 1
    app = create_app(workspace)
    selection = Selection(id='s', ids=['remote-record'], unit='example', snapshot_ids=['s1'], dataset_ids=['fixture'], created_at='now',
                          query={'population_scope': 'complete'})
    prepared = app.state.selection_records(selection, prepare_media=True)[0].assets[0]
    path = Path(prepared.uri)
    assert path.is_file() and path.read_bytes() == original
    assert path.parent == (workspace / 'work/media-cache').resolve() and path.stem == hashlib.sha256(original).hexdigest()
    assert prepared.metadata['source_ref'] == ref
    outside=workspace.parent/(workspace.name+'-untouched-source.png')
    if cache_defect=='corrupt':path.write_bytes(b'Corrupt synthetic cache')
    elif cache_defect=='symlink':
        outside.write_bytes(b'Untouched synthetic external source');path.unlink();path.symlink_to(outside)
    elif cache_defect=='fifo':path.unlink();os.mkfifo(path)
    again = app.state.selection_records(selection, prepare_media=True)[0].assets[0]
    assert again.uri == prepared.uri  # content-addressed: a second run reuses the same file
    assert not path.is_symlink() and path.read_bytes()==original
    if cache_defect=='symlink':assert outside.read_bytes()==b'Untouched synthetic external source'


@pytest.mark.parametrize('cache_defect',['corrupt','symlink','fifo'])
def test_general_resolver_handoff_repairs_cache_before_processors_read_it(workspace,pack,monkeypatch,cache_defect):
    import yaml
    original=png_bytes();digest=hashlib.sha256(original).hexdigest()
    pack.dataset.adapter_config={'path':'source-table.jsonl'}
    pack.records=[Record(id='remote-record',dataset_id='fixture',release_id='r1',snapshot_id='s1',
        assets=[Asset(id='remote-one',dataset_id='fixture',release_id='r1',modality='image',uri='file/one.png',sha256=digest)])]
    (workspace/'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(pack.dataset.model_dump()))
    (workspace/'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    monkeypatch.setattr('dataset_atlas.adapters.resolve_dataset_asset',lambda _d,ref,**_:MediaHandle(original,'image/png',digest,ref))
    app=create_app(workspace)
    selection=Selection(id='s',ids=['remote-record'],unit='example',snapshot_ids=['s1'],dataset_ids=['fixture'],created_at='now')
    path=Path(app.state.selection_records(selection,prepare_media=True)[0].assets[0].uri)
    external=workspace.parent/(workspace.name+'-untouched.png')
    if cache_defect=='corrupt':path.write_bytes(b'corrupt fixture')
    else:
        path.unlink()
        if cache_defect=='symlink':external.write_bytes(b'untouched fixture');path.symlink_to(external)
        else:os.mkfifo(path)
    app.state.selection_records(selection,prepare_media=True)
    assert path.read_bytes()==original and not path.is_symlink()
    if cache_defect=='symlink':assert external.read_bytes()==b'untouched fixture'


def test_changed_declared_local_original_is_refused(workspace,pack):
    original=png_bytes();directory=workspace/'work/packs/fixture/media';directory.mkdir()
    (directory/'test.png').write_bytes(b'changed fixture')
    for row in pack.records:
        for asset in row.assets:asset.sha256=hashlib.sha256(original).hexdigest()
    (workspace/'work/packs/fixture/pack.json').write_text(pack.model_dump_json())
    app=create_app(workspace)
    selection=Selection(id='s',ids=['r0'],unit='example',snapshot_ids=['s1'],dataset_ids=['fixture'],created_at='now')
    with pytest.raises(ValueError,match='selected asset checksum'):app.state.selection_records(selection,prepare_media=True)
