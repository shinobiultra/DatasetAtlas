import random

from dataset_atlas.models import Asset, Record
from dataset_atlas.preparation.sampling import PreviewSampler


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

