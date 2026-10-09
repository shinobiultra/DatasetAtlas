"""The modality derivation reads only what a preview pack contains."""
import importlib.util
from pathlib import Path

from dataset_atlas.models import Asset, Record

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/derive_catalogue_modalities.py'
spec = importlib.util.spec_from_file_location('derive_catalogue_modalities', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakePack:
    def __init__(self, records):
        self.records = records


def record(rid, assets=(), **fields):
    return Record(id=rid, dataset_id='d', release_id='r', snapshot_id='s', assets=list(assets), asset_ids=[a.id for a in assets], **fields)


def asset(aid, modality):
    return Asset(id=aid, dataset_id='d', release_id='r', modality=modality, uri=f'media/{aid}')


def test_asset_kinds_and_text_fields_are_read_from_records_in_a_fixed_order():
    pack = FakePack([record('1', [asset('a', 'video')], question='what?'), record('2', [asset('b', 'image')])])
    assert module.derive(pack) == ['image', 'video', 'text']


def test_no_assets_and_no_text_derives_nothing_instead_of_guessing():
    assert module.derive(FakePack([record('1')])) == []


def test_text_only_records_are_text():
    assert module.derive(FakePack([record('1', text='a prompt')])) == ['text']
