"""The public guide: how-to-get states, paper provenance without private fields, and schemas without record values."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from dataset_atlas.exports import build_publication
from dataset_atlas.exports.guide import HOW_TO_GET, build_guide, how_to_get, schema_document, write_schemas
from dataset_atlas.exports.security import ExchangeError
from dataset_atlas.models import Dataset, FieldDescriptor, Pack, Record

ROOT = Path(__file__).resolve().parents[2]


def entry(dataset_id="toy", **coverage) -> Dataset:
    return Dataset(id=dataset_id, name=dataset_id, release="r1", snapshot_id="s1", coverage=coverage)


@pytest.mark.parametrize("coverage, recipe, in_site, state", [
    ({"access": "public", "preview": "complete_target"}, True, True, "in_site"),
    ({"access": "public", "preview": "complete_target"}, True, False, "fetch_with_atlas"),
    ({"access": "gated", "preview": "complete_target"}, True, False, "fetch_after_terms"),
    ({"access": "public", "preview": "complete_target"}, False, False, "prepared_by_maintainers_only"),
    ({"access": "gated", "preview": "none"}, False, False, "accept_terms"),
    ({"access": "request_required", "preview": "none"}, False, False, "request_from_authors"),
    ({"access": "author_request_required", "preview": "none"}, False, False, "request_from_authors"),
    ({"access": "unreleased", "preview": "none"}, False, False, "unreleased"),
    ({"access": "public", "preview": "none"}, False, False, "public_no_adapter"),
    ({"access": "unverified", "preview": "none"}, False, False, "source_unverified"),
    ({"access": "source_release_unverified", "preview": "none"}, False, False, "source_unverified"),
])
def test_how_to_get_is_computed_from_access_recipe_and_preview(coverage, recipe, in_site, state):
    result = how_to_get(entry(**coverage), has_recipe=recipe, in_site=in_site)
    assert result["state"] == state and result["summary"] == HOW_TO_GET[state]
    assert ("commands" in result) == (state in {"fetch_with_atlas", "fetch_after_terms"})


def test_a_recipe_that_needs_a_local_credential_marks_the_source_as_gated_whatever_the_catalogue_says():
    result = how_to_get(entry(access="unverified", preview="complete_target"), has_recipe=True, in_site=False, needs_credentials=True)
    assert result["state"] == "fetch_after_terms" and result["commands"]


def test_fetch_commands_name_the_dataset_and_a_dry_run_comes_first():
    commands = how_to_get(entry("mnist", access="public"), has_recipe=True, in_site=False)["commands"]
    assert commands == ["atlas previews fetch --dataset mnist", "atlas previews fetch --dataset mnist --execute"]


def test_a_dataset_without_a_recipe_never_gets_a_fetch_command():
    assert "commands" not in how_to_get(entry(access="public", preview="none"), has_recipe=False, in_site=False)


def pack_with_secret_values() -> tuple[Dataset, Pack]:
    dataset = entry(access="public", preview="complete_target", preview_count=1, total_count=9, unit="example")
    fields = [FieldDescriptor(id="source.label", name="label", dtype="category", namespace="source", values=["cat", "dog"], description="Author label"),
              FieldDescriptor(id="source.big", name="big", dtype="category", namespace="source", values=list(range(31))),
              FieldDescriptor(id="source.note", name="note", dtype="string", namespace="source")]
    record = Record(id="toy:example:1", dataset_id="toy", release_id="r1", snapshot_id="s1", text="PRIVATE RECORD TEXT", source={"note": "PRIVATE SOURCE VALUE"})
    return dataset, Pack(dataset=dataset, fields=fields, records=[record], sampling={"method": "first", "seed": 0, "local_cache": "/home/x/cache"})


def test_a_schema_holds_field_names_and_declared_values_and_never_record_content():
    dataset, pack = pack_with_secret_values()
    document = schema_document(dataset, pack)
    text = json.dumps(document)
    assert "PRIVATE" not in text and "/home/" not in text
    by_id = {field["id"]: field for field in document["fields"]}
    assert by_id["source.label"]["values"] == ["cat", "dog"]
    assert "values" not in by_id["source.big"], "a long value list is not a schema"
    assert document["sampling"] == {"method": "first", "seed": 0}, "only allowlisted sampling keys are published"
    assert (document["preview_count"], document["total_count"], document["field_count"]) == (1, 9, 3)


def registry_with(tmp_path: Path, dataset: Dataset, *, recipe=False, paper=True) -> Path:
    registry = tmp_path / "registry"
    (registry / "papers").mkdir(parents=True)
    (registry / "recipes").mkdir()
    if recipe:
        (registry / "recipes" / f"{dataset.id}.yaml").write_text("release: r1\n")
    if paper:
        (registry / "papers/paper-1.yaml").write_text(yaml.safe_dump({
            "paper_id": "paper-1", "title": "A Paper", "year": "2024", "doi": "10.1/x", "url": "https://arxiv.org/abs/1",
            "sources": [{"relative_path": "/home/private/files/a.pdf"}], "review_note": "internal note"}))
    return registry


def test_the_guide_lists_papers_by_title_without_private_review_fields(tmp_path):
    dataset = entry(access="public", preview="none")
    dataset.paper_ids = ["paper-1", "paper-missing"]
    document = json.loads(build_guide([dataset], registry_dir=registry_with(tmp_path, dataset), schema_dir=tmp_path / "none", published=set()))
    papers = document["datasets"]["toy"]["papers"]
    assert papers == [{"paper_id": "paper-1", "title": "A Paper", "year": "2024", "doi": "10.1/x", "url": "https://arxiv.org/abs/1"}]
    assert "review_note" not in json.dumps(document) and "/home/" not in json.dumps(document)


def test_a_committed_schema_reaches_the_guide_and_a_schema_with_a_local_path_is_refused(tmp_path):
    dataset, pack = pack_with_secret_values()
    schemas = tmp_path / "schemas"
    schemas.mkdir()
    (schemas / "toy.json").write_text(json.dumps(schema_document(dataset, pack)))
    registry = registry_with(tmp_path, dataset, paper=False)
    document = json.loads(build_guide([dataset], registry_dir=registry, schema_dir=schemas, published=set()))
    assert document["datasets"]["toy"]["schema"]["field_count"] == 3 and "id" not in document["datasets"]["toy"]["schema"]
    bad = json.loads((schemas / "toy.json").read_text())
    bad["fields"][0]["description"] = "see /home/researcher/private/notes"
    (schemas / "toy.json").write_text(json.dumps(bad))
    with pytest.raises(ExchangeError):
        build_guide([dataset], registry_dir=registry, schema_dir=schemas, published=set())


def test_a_schema_for_another_dataset_is_refused(tmp_path):
    dataset, pack = pack_with_secret_values()
    schemas = tmp_path / "schemas"
    schemas.mkdir()
    wrong = schema_document(dataset, pack)
    wrong["id"] = "other"
    (schemas / "toy.json").write_text(json.dumps(wrong))
    with pytest.raises(ExchangeError, match="Invalid public schema"):
        build_guide([dataset], registry_dir=registry_with(tmp_path, dataset, paper=False), schema_dir=schemas, published=set())


def test_write_schemas_replaces_stale_files_and_skips_a_dataset_without_a_pack(tmp_path):
    dataset, pack = pack_with_secret_values()

    class Registry:
        def datasets(self):
            return [dataset, entry("nopack", preview="complete_target", preview_count=3), entry("nothing", preview="none")]

        def pack(self, dataset_id):
            if dataset_id == "toy":
                return pack
            raise FileNotFoundError(dataset_id)

    out = tmp_path / "out"
    out.mkdir()
    (out / "stale.json").write_text(json.dumps({"schema_version": "1.0", "id": "stale", "fields": []}))
    assert write_schemas(Registry(), out) == ["toy"]
    assert sorted(p.name for p in out.iterdir()) == ["toy.json"]


def test_publication_writes_the_guide_beside_the_catalogue(tmp_path):
    shutil_registry = tmp_path / "registry"
    (shutil_registry / "datasets").mkdir(parents=True)
    (shutil_registry / "papers").mkdir()
    (shutil_registry / "recipes").mkdir()
    dataset = entry(access="public", preview="none")
    (shutil_registry / "datasets/toy.yaml").write_text(yaml.safe_dump(json.loads(dataset.model_dump_json())))
    (shutil_registry / "publication.json").write_text(json.dumps({"schema_version": "1.0", "datasets": {}}))
    (tmp_path / "examples/approved-packs").mkdir(parents=True)
    report = build_publication(shutil_registry, tmp_path / "examples/approved-packs", tmp_path / "site", shutil_registry / "publication.json")
    guide = json.loads((report.output_dir / "guide.json").read_text())
    assert guide["datasets"]["toy"]["how_to_get"]["state"] == "public_no_adapter"
    assert report.catalogue_count == 1


def test_every_committed_schema_belongs_to_a_catalogue_dataset_and_is_publishable():
    from dataset_atlas.exports.guide import MAX_SCHEMA_BYTES
    ids = {path.stem for path in (ROOT / "registry/datasets").glob("*.yaml")}
    files = sorted(path for path in (ROOT / "examples/public-schema").glob("*.json") if path.name != "coverage.json")
    assert files, "run `atlas publish schemas` and commit the result"
    for path in files:
        document = json.loads(path.read_text())
        assert path.stem in ids and document["id"] == path.stem, path.name
        assert path.stat().st_size <= MAX_SCHEMA_BYTES


def test_the_committed_coverage_snapshot_agrees_with_the_coverage_matrix():
    """The public catalogue shows the merged coverage; a stale snapshot would misreport which datasets have previews."""
    import csv
    from dataset_atlas.exports.guide import load_coverage
    snapshot = load_coverage(ROOT / "examples/public-schema")
    rows = {row["dataset_id"]: row for row in csv.DictReader((ROOT / "reports/dataset_coverage.csv").open(newline="", encoding="utf-8"))}
    assert set(snapshot) == set(rows), "run `atlas publish schemas` after the coverage matrix changes and commit the result"
    for dataset_id, row in rows.items():
        coverage = snapshot[dataset_id]
        assert (coverage["preview"], str(coverage["preview_count"]), coverage["access"], coverage["adapter"]) == (row["preview"], row["preview_count"], row["access"], row["adapter"]), dataset_id


def test_the_build_shows_merged_coverage_where_the_registry_yaml_predates_preparation(tmp_path):
    registry = tmp_path / "registry"
    for name in ("datasets", "papers", "recipes"):
        (registry / name).mkdir(parents=True)
    dataset = entry(access="gated", preview="none", adapter="not_started")
    (registry / "datasets/toy.yaml").write_text(yaml.safe_dump(json.loads(dataset.model_dump_json())))
    (registry / "publication.json").write_text(json.dumps({"schema_version": "1.0", "datasets": {}}))
    (tmp_path / "examples/approved-packs").mkdir(parents=True)
    state = tmp_path / "examples/public-schema"
    state.mkdir()
    merged = dataset.coverage.model_dump(mode="json") | {"preview": "complete_target", "adapter": "tested", "preview_count": 100}
    (state / "coverage.json").write_text(json.dumps({"schema_version": "1.0", "datasets": {"toy": merged}}))
    report = build_publication(registry, tmp_path / "examples/approved-packs", tmp_path / "site", registry / "publication.json")
    catalogue = json.loads((report.output_dir / "catalogue.json").read_text())
    assert (catalogue[0]["coverage"]["preview"], catalogue[0]["coverage"]["adapter"], catalogue[0]["coverage"]["preview_count"]) == ("complete_target", "tested", 100)
    assert json.loads((report.output_dir / "guide.json").read_text())["datasets"]["toy"]["how_to_get"]["state"] == "prepared_by_maintainers_only"


def test_a_public_mirror_that_reads_with_a_credential_is_not_called_gated():
    assert how_to_get(entry(access="public", preview="complete_target"), has_recipe=True, in_site=False, needs_credentials=True)["state"] == "fetch_with_atlas"


def test_write_schemas_deletes_only_schemas_it_wrote_and_never_when_nothing_was_written(tmp_path):
    dataset, pack = pack_with_secret_values()

    class Registry:
        def __init__(self, packs):
            self.packs = packs

        def datasets(self):
            return [dataset]

        def pack(self, dataset_id):
            if dataset_id in self.packs:
                return pack
            raise FileNotFoundError(dataset_id)

    out = tmp_path / "out"
    out.mkdir()
    (out / "final-status.json").write_text('{"status": "x"}')
    (out / "gone.json").write_text(json.dumps({"schema_version": "1.0", "id": "gone", "fields": []}))
    assert write_schemas(Registry({"toy"}), out) == ["toy"]
    assert sorted(p.name for p in out.iterdir()) == ["final-status.json", "toy.json"]
    with pytest.raises(ExchangeError, match="refusing"):
        write_schemas(Registry(set()), out)
    assert (out / "toy.json").exists()
