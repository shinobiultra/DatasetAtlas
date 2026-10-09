"""A preview that must hold every declared stratum in equal share, with the stratum counted from the source field of each record."""
import pytest

from dataset_atlas.models import Asset, Record
from dataset_atlas.preparation.sampling import PreviewSampler

STRATA = {"field": "aspect", "values": ["a", "b", "c", "d", "e"]}


def record(index: int, aspect: str) -> Record:
    asset = Asset(id=f"img{index}", dataset_id="d", release_id="r", modality="image", uri=f"u/{index}")
    return Record(id=f"r{index}", dataset_id="d", release_id="r", snapshot_id="s", source={"aspect": aspect}, assets=[asset], asset_ids=[asset.id])


def population(sizes: dict[str, int]) -> list[Record]:
    records, index = [], 0
    for aspect, count in sizes.items():
        for _ in range(count):
            records.append(record(index, aspect))
            index += 1
    return records


def test_the_first_hundred_candidates_hold_every_stratum_in_equal_share_even_when_populations_differ():
    sampler = PreviewSampler(250, seed=0, stratify=STRATA)
    for item in population({"a": 4000, "b": 700, "c": 3000, "d": 1200, "e": 2600}):
        sampler.add(item)
    first = sampler.records()[:100]
    counts = {aspect: sum(r.source["aspect"] == aspect for r in first) for aspect in STRATA["values"]}
    assert counts == {aspect: 20 for aspect in STRATA["values"]}
    description = sampler.description("rel")
    assert description["stratified_by"] == "aspect" and description["strata_population"]["b"] == 700
    assert description["population_count"] == 11500 and description["returned_count"] == 250


def test_the_selection_does_not_depend_on_record_order():
    items = population({"a": 300, "b": 300, "c": 300, "d": 300, "e": 300})
    forward, backward = PreviewSampler(100, stratify=STRATA), PreviewSampler(100, stratify=STRATA)
    for item in items:
        forward.add(item)
    for item in reversed(items):
        backward.add(item)
    assert [r.id for r in forward.records()] == [r.id for r in backward.records()]


def test_a_short_stratum_gives_what_it_has_and_never_borrows():
    sampler = PreviewSampler(100, stratify=STRATA)
    for item in population({"a": 5, "b": 400, "c": 400, "d": 400, "e": 400}):
        sampler.add(item)
    records = sampler.records()
    assert sum(r.source["aspect"] == "a" for r in records) == 5 and len(records) == 85


def test_a_record_outside_the_declared_strata_is_an_error_not_a_silent_drop():
    sampler = PreviewSampler(100, stratify=STRATA)
    with pytest.raises(ValueError, match="outside the declared preview strata"):
        sampler.add(record(0, "zzz"))


@pytest.mark.parametrize("spec", [{"field": "aspect", "values": ["a"]}, {"field": "aspect", "values": ["a", "a"]}, {"values": ["a", "b"]}])
def test_a_malformed_stratification_is_refused(spec):
    with pytest.raises(ValueError):
        PreviewSampler(100, stratify=spec)
