import random
import hashlib
from io import BytesIO

import pytest
from PIL import Image

from dataset_atlas.models import Asset, Record
from dataset_atlas.preparation.sampling import PreviewSampler, AssetFirstPreviewSampler, select_verified_remote_preview


def record(i, group=None):
    assets = [] if group is None else [Asset(id=f'image-{group}', dataset_id='fixture', release_id='r', modality='image', uri=f'{group}.png')]
    return Record(id=str(i), dataset_id='fixture', release_id='r', snapshot_id='s',
                  asset_ids=[a.id for a in assets], assets=assets)


def test_sample_is_order_independent_distinct_and_bounded():
    records = [record(i, i % 137) for i in range(10000)]
    forward, reverse = PreviewSampler(), PreviewSampler()
    shuffled = list(records)
    random.Random(7).shuffle(shuffled)
    for first, second in zip(records, shuffled):
        forward.add(first)
        reverse.add(second)
        assert len(forward.selected) <= 100
        assert len(forward.heap) <= 100
    assert forward.records() == reverse.records()
    assert len({r.asset_ids[0] for r in forward.records()}) == 100
    assert forward.population_count == 10000
    assert max(int(r.id) for r in forward.records()) > 1000
    # Sampling never creates a resized or re-encoded image reference.
    assert all(r.assets[0].representation == 'original' for r in forward.records())


def test_text_populations_small_populations_and_seeds():
    a, b = PreviewSampler(seed=0), PreviewSampler(seed=11)
    for i in range(200):
        a.add(record(i)); b.add(record(i))
    assert len(a.records()) == len(b.records()) == 100
    assert a.records() != b.records()
    small = PreviewSampler()
    for i in range(12): small.add(record(i))
    assert {r.id for r in small.records()} == {str(i) for i in range(12)}
    assert small.description('release')['population_count'] == 12
    assert small.description('release', 'asset')['unit'] == 'asset'


def test_example_grouping_reaches_target_when_many_questions_share_images():
    sampler = PreviewSampler(100, group_by='example')
    for index in range(1600):
        sampler.add(record(index, index // 50))
    assert len(sampler.records()) == 100
    assert len({item.id for item in sampler.records()}) == 100
    assert len({item.asset_ids[0] for item in sampler.records()}) <= 32
    assert sampler.description('release')['method'] == 'sha256_bottom_k_example'


def test_asset_first_sampling_fills_examples_without_losing_distinct_images():
    sampler = AssetFirstPreviewSampler(100)
    for index in range(1600):
        sampler.add(record(index, index // 50))
    result = sampler.records()
    assert len(result) == len({item.id for item in result}) == 100
    assert len({item.asset_ids[0] for item in result}) == 32
    assert sampler.description('release')['method'] == 'sha256_asset_first_with_example_fill'


def test_remote_preview_skips_path_only_slots_and_pins_checked_hashes():
    output = BytesIO()
    Image.new('RGB', (2, 2), 'red').save(output, format='PNG')
    data = output.getvalue()
    class Handle:
        sha256 = hashlib.sha256(data).hexdigest()
    handle = Handle()
    handle.data = data
    candidates = [record(0, 'missing'), record(1, 'present'), record(2, 'later')]
    def resolve(ref):
        if ref == 'missing.png':
            raise FileNotFoundError('source has a path but no bytes')
        return handle
    progress = []
    selected, report = select_verified_remote_preview(candidates, resolve, 2,
        on_progress=lambda **values: progress.append(values))
    assert [r.id for r in selected] == ['1', '2']
    assert all(r.assets[0].sha256 == handle.sha256 for r in selected)
    assert report['unavailable_candidate_records'] == 1
    assert report['verified_preview_assets'] == 2
    assert progress == [{'verified_records': 2, 'verified_assets': 2, 'candidates_checked': 3}]
    with pytest.raises(ValueError, match='Only 2 of 3'):
        select_verified_remote_preview(candidates, resolve, 3)
