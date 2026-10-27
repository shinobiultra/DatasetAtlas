"""Synthetic inventory units: no source content or remote image reads."""
import hashlib
import json
from pathlib import Path
from collections import Counter

import pytest

from dataset_atlas.adapters.multitrust import MultiTrustAdapter
from dataset_atlas.models import Dataset


def configured(tmp_path, *, inventory_tasks=None):
    query = tmp_path / "queries.json"
    query.write_text(json.dumps([{"prompt": "Synthetic question", "image": "q.png"}]))
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"files": {
        name: {"bytes": 7, "sha256": "a" * 64}
        for name in ["queries/q.png", "image_only/category/b.png", "image_only/category/a.png",
                     "unpaired/z.png", "pool/x.png", "figure.png"]
    }}))
    config = {
        "tasks": [{"task": "query", "aspect": "safety", "query_file": "queries.json",
                   "media": [{"template": "queries/{image}"}], "join_basis": "key_in_query_row"}],
        "source_files": [{"source_name": "queries.json", "path": str(query),
                          "sha256": hashlib.sha256(query.read_bytes()).hexdigest()}],
        "media_inventory_path": str(inventory),
        "media_inventory_sha256": hashlib.sha256(inventory.read_bytes()).hexdigest(),
    }
    if inventory_tasks is not None:
        config["inventory_tasks"] = inventory_tasks
    return MultiTrustAdapter(Dataset(id="multitrust", name="Synthetic suite", release="fixture",
                                    snapshot_id="fixture", adapter="multitrust", adapter_config=config))


SPECS = [
    {"task": "image_only", "aspect": "safety", "prefix": "image_only", "unit_kind": "image_only_example",
     "join_basis": "image_only_no_query_file", "toolkit_tasks": ["image-description"]},
    {"task": "query", "aspect": "safety", "prefix": "unpaired", "unit_kind": "unpaired_image",
     "join_basis": "none_listdir_order_in_toolkit", "related_query_task": "query"},
    {"task": "shared", "aspect": "safety", "prefix": "pool", "unit_kind": "source_pool_image",
     "join_basis": "none_random_choice_in_toolkit"},
]


def records(adapter):
    source = adapter.prepare(adapter.plan(100, 1_000_000))
    return adapter.iter_records(source).records


def test_inventory_units_preserve_query_ids_and_do_not_fabricate_pairings(tmp_path):
    legacy = records(configured(tmp_path))
    adapter = configured(tmp_path, inventory_tasks=SPECS)
    result = records(adapter)
    assert len(result) == 5
    assert result[0].id == legacy[0].id
    assert result[0].source["unit_kind"] == "query_row"
    assert [r.source["image_file"] for r in result[1:]] == [
        "image_only/category/a.png", "image_only/category/b.png", "unpaired/z.png", "pool/x.png"]
    assert all(r.question is None and r.text is None and r.choices == [] for r in result[1:])
    assert all(r.source["query_file"] is None for r in result[1:])
    assert result[1].source["source_category"] == "category"
    assert result[1].source["_atlas_origin"]["inventory_sha256"] == adapter.config["media_inventory_sha256"]
    assert result[3].source["related_query_task"] == "query"
    assert result[3].source["join_basis"] == "none_listdir_order_in_toolkit"
    assert len({r.id for r in result}) == 5
    assert result[1].assets[0].sha256 == "a" * 64
    report = adapter.join_report()
    assert report["query_rows"] == 1
    assert report["inventory_rows"] == 4
    assert len(report["inventory_images_without_a_query_row"]) == 5
    assert report["inventory_images_without_a_record"] == ["figure.png"]


@pytest.mark.parametrize("specs", [
    [SPECS[0], SPECS[0]],
    [{**SPECS[0], "prefix": "../image_only"}],
    [{**SPECS[0], "prefix": "missing"}],
    [{**SPECS[0], "prefix": "queries"}],
    [{**SPECS[0], "unit_kind": "query_row"}],
])
def test_ambiguous_missing_or_overlapping_inventory_units_are_refused(tmp_path, specs):
    with pytest.raises(ValueError):
        records(configured(tmp_path, inventory_tasks=specs))


def test_standard_recipe_retains_native_image_units_and_shared_preview_stratum(tmp_path):
    import yaml
    from dataset_atlas.preparation.sampling import PreviewSampler
    recipe = yaml.safe_load((Path(__file__).resolve().parents[2] / "registry/recipes/multitrust.yaml").read_text())
    fixture = configured(tmp_path)
    config = recipe["adapter_config"]
    config["tasks"] = fixture.config["tasks"]
    config["source_files"] = fixture.config["source_files"]
    image_files = {"queries/q.png": {"bytes": 7, "sha256": "a" * 64}}
    for spec in config["inventory_tasks"]:
        image_files[spec["prefix"] + "/synthetic.png"] = {"bytes": 7, "sha256": "b" * 64}
    inventory = tmp_path / "complete-synthetic-inventory.json"
    inventory.write_text(json.dumps({"files": image_files}))
    config["media_inventory_path"] = str(inventory)
    config["media_inventory_sha256"] = hashlib.sha256(inventory.read_bytes()).hexdigest()
    adapter = MultiTrustAdapter(Dataset(id="multitrust", name="Synthetic full recipe", release=recipe["release"],
                                       snapshot_id=recipe["snapshot_id"], adapter="multitrust", adapter_config=config))
    result = records(adapter)
    assert len(result) == 10
    assert Counter(record.source["unit_kind"] for record in result) == {
        "query_row": 1, "image_only_example": 3, "unpaired_image": 1, "source_pool_image": 5}
    assert all(record.question is None and record.text is None for record in result[1:])
    sampler = PreviewSampler(250, stratify=config["preview_sampling"]["stratify_by"])
    for record in result:
        sampler.add(record)
    assert sampler.population_count == 10
    assert len(sampler.records()) == 10
    assert sampler.description(recipe["release"])["strata_population"]["shared"] == 1


@pytest.mark.parametrize("limit,want_error,want_calls,want_bytes", [
    (10, ValueError, 1, 6), (100, TimeoutError, 3, 18),
])
def test_failed_original_reads_remain_charged_and_retries_respect_transfer_cap(
    tmp_path, monkeypatch, limit, want_error, want_calls, want_bytes
):
    adapter = configured(tmp_path)
    adapter.config.update(remote_cache_root=str(tmp_path / "cache"), remote_cache_bytes=1000,
                          media_base_url="https://example.test/source", media_allowed_hosts=["example.test"])
    adapter.preparation_transfer_limit = limit
    source = adapter.prepare(adapter.plan(100, 1_000_000))
    calls = []

    def interrupted(fetcher, *args, **kwargs):
        calls.append(True)
        fetcher.bytes_fetched += 6
        raise TimeoutError("Synthetic partial image read")

    monkeypatch.setattr("dataset_atlas.adapters.multitrust.HttpsFetcher.fetch", interrupted)
    monkeypatch.setattr("dataset_atlas.adapters.multitrust.time.sleep", lambda _: None)
    with pytest.raises(want_error):
        adapter.resolve_asset(source, "file/queries/q.png")
    assert len(calls) == want_calls
    assert adapter.media_bytes_fetched == want_bytes
