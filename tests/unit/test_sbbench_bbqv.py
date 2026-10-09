"""BBQ-V (ucf-crcv/BBQ-V, catalogue entry `sbbench`) through the native `remote_columnar` adapter.

Every shard in this file is SYNTHETIC: it copies only the layout of the gated release (four file groups named
`real-`, `synthetic-`, `test-` and `test2-`, an embedded `file_name` image struct, integer class-label columns,
upstream ids that repeat across groups, and a `test` group without answer columns). No gated content is copied
into the repository. What the real release holds is recorded separately, with counts and byte totals, in
`reports/bbq-v-live-verification-20261008.json`, and the tests at the end check that the recipe, the registry entry
and that receipt agree with each other.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from PIL import Image

from dataset_atlas.adapters.remote_columnar import RemoteColumnarAdapter
from dataset_atlas.models import Dataset

ROOT = Path(__file__).resolve().parents[2]
RECIPE_PATH = ROOT / "registry/recipes/sbbench.yaml"
ENTRY_PATH = ROOT / "registry/datasets/sbbench.yaml"
RECEIPT_PATH = ROOT / "reports/bbq-v-live-verification-20261008.json"
BASE_COMMIT = "82e5a9c643d030ecb567c9fb2767f4a457200499"  # the entry as the gate check left it
REVISION = "a1c78b8f73bc40408993414e3d94714a6a9169d3"
HOSTS = ["huggingface.co", "cas-bridge.xethub.hf.co", "us.aws.cdn.hf.co"]
TOKEN_PATTERN = re.compile(r"hf_[A-Za-z0-9]{20,}")

# group -> (shards, rows per shard, answer columns present)
GROUPS = {"real": (2, 32, True), "synthetic": (1, 24, True), "test": (2, 32, False), "test2": (1, 40, True)}
TOTAL_ROWS = sum(shards * rows for shards, rows, _ in GROUPS.values())
CLASS_LABELS = {
    "category": ["Age", "Disability_status", "Gender_identity", "Nationality", "Physical_appearance",
                 "Race_ethnicity", "Religion", "SES", "Sexual_orientation"],
    "question_polarity": ["neg", "nonneg"],
    "label": ["0", "1", "2"],
}


def recipe() -> dict:
    return yaml.safe_load(RECIPE_PATH.read_text())


def jpeg(seed: int) -> bytes:
    """A noisy JPEG of a few tens of kilobytes, so that image columns dominate the shard as they do in the real release."""
    import random
    width, height = 256 + seed % 7, 192 + seed % 5
    buffer = io.BytesIO()
    Image.frombytes("RGB", (width, height), random.Random(seed).randbytes(width * height * 3)).save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def upstream_id(item: int) -> str:
    return f"{item % 9 + 1:02d}_01_{item:04d}_{item % 2 + 1}_01"


def write_release(directory: Path, *, mutate=None) -> tuple[list[dict], dict[str, bytes], dict[str, bytes]]:
    """Synthetic shards in the real naming scheme. Returns file entries, payloads by URL, original bytes by row key."""
    entries, payloads, originals = [], {}, {}
    directory.mkdir(parents=True, exist_ok=True)
    for group, (shards, per_shard, answers) in GROUPS.items():
        for shard in range(shards):
            rows = []
            for local in range(per_shard):
                item = shard * per_shard + local  # the same item numbers (hence ids) recur in every group
                # `test` names each image after its row; the other groups reuse a file name (and its bytes) for several rows.
                name = f"{upstream_id(item)}.jpg" if group == "test" else f"{item % 2}_nonneg_ambig_{item // 4}.jpg"
                image = jpeg(int(hashlib.sha256(f"{group}/{name}".encode()).hexdigest()[:6], 16))
                row = {"file_name": {"bytes": image, "path": name}, "id": upstream_id(item), "category": item % 9,
                       "additional_metadata": "{'subcategory': 'None', 'stereotyped_groups': ['old'], 'version': 'a'}",
                       "question_polarity": item % 2, "context": f"Two people, item {item}.", "question": "Who is it?"}
                if answers:
                    row.update(ans0="first", ans1="second", ans2="unknown", label=item % 3)
                rows.append(row)
                originals[f"{group}-{shard}-{local}"] = image
            if mutate:
                mutate(group, shard, rows)
            names = ["file_name", "id", "category", "additional_metadata", "question_polarity", "context", "question"]
            names += ["ans0", "ans1", "ans2", "label"] if answers else []
            table = pa.Table.from_pylist(rows)
            table = table.select(names)
            features = {key: {"names": value, "_type": "ClassLabel"} for key, value in CLASS_LABELS.items() if key in names}
            table = table.replace_schema_metadata({"huggingface": json.dumps({"info": {"features": features}})})
            name = f"data/{group}-{shard:05d}-of-{shards:05d}.parquet"
            target = directory / name.replace("/", "_")
            pq.write_table(table, target, row_group_size=8)
            payload = target.read_bytes()
            url = f"https://huggingface.co/datasets/ucf-crcv/BBQ-V/resolve/{REVISION}/{name}"
            payloads[url] = payload
            entries.append({"source_name": name, "url": url, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                            "etag": f'"{hashlib.sha256(payload + b"etag").hexdigest()}"'})
    return entries, payloads, originals


def serve(monkeypatch, payloads: dict[str, bytes]) -> list[tuple[str, int, int]]:
    """Answer shard reads from memory; record every network read as (url, offset, length).

    The real reader keeps each verified range in a bounded cache, so a repeated identical range costs nothing;
    this stand-in does the same."""
    calls: list[tuple[str, int, int]] = []
    seen: set[tuple[str, int, int]] = set()

    class Reader(io.BytesIO):
        def __init__(self, url, **kwargs):
            super().__init__(payloads[url])
            self.url, self.size, self.bytes_fetched = url, len(payloads[url]), 0
            self.byte_budget = kwargs["byte_budget"]
            assert kwargs.get("credential_profile") == "huggingface"  # the gated profile reaches every ranged read

        def read(self, size=-1):
            start = self.tell()
            data = super().read(size)
            key = (self.url, start, len(data))
            if key in seen:
                return data
            if self.bytes_fetched + len(data) > self.byte_budget:
                raise ValueError("Remote reads exceed transfer budget")
            seen.add(key)
            self.bytes_fetched += len(data)
            calls.append(key)
            return data

    monkeypatch.setattr("dataset_atlas.adapters.remote_columnar.HttpsRangeReader", Reader)
    return calls


def adapter_for(tmp_path: Path, entries: list[dict], **config) -> RemoteColumnarAdapter:
    """The adapter configured exactly as the real recipe configures it, over the synthetic shards."""
    recipe_config = recipe()["adapter_config"]
    options = {key: value for key, value in recipe_config.items() if key not in {"remote_files", "remote_cache_root"}}
    options.update(remote_files=entries, remote_cache_root=str(tmp_path / "cache"), allowed_hosts=HOSTS,
                   metadata_transfer_bytes=50_000_000, credential_profile="huggingface")
    options.update(config)
    dataset = Dataset(id="sbbench", name="SBBench", release=recipe()["release"], snapshot_id="fixture", adapter="remote_columnar",
                      adapter_config=options)
    return RemoteColumnarAdapter(dataset)


@pytest.fixture
def release(tmp_path, monkeypatch):
    entries, payloads, originals = write_release(tmp_path)
    calls = serve(monkeypatch, payloads)
    return entries, payloads, originals, calls


def all_records(adapter):
    source = adapter.prepare(adapter.plan(1000, 500_000_000))
    return source, list(adapter.iter_all_records(source, workers=2))


# --- the recipe -------------------------------------------------------------------------------------------------


def test_recipe_pins_every_shard_of_one_revision_and_names_the_credential_profile():
    document = recipe()
    files = document["adapter_config"]["remote_files"]
    assert document["adapter"] == "remote_columnar" and document["credential_profile"] == "huggingface"
    assert len(files) == 45 and len({entry["source_name"] for entry in files}) == 45
    for entry in files:
        assert entry["url"] == f"https://huggingface.co/datasets/ucf-crcv/BBQ-V/resolve/{REVISION}/{entry['source_name']}"
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) and re.fullmatch(r'"[0-9a-f]{64}"', entry["etag"])
        assert type(entry["bytes"]) is int and entry["bytes"] > 0
    assert REVISION in document["release"]
    # A huggingface.co/datasets URL as source_url would send `auto` planning to the sampled route, which builds no complete index.
    assert "source_url" not in document
    hosts = document["adapter_config"]["allowed_hosts"]
    assert "huggingface.co" in hosts and all(host.endswith("hf.co") or host == "huggingface.co" for host in hosts)
    assert sum(entry["bytes"] for entry in files) < 12_500_000_000


def test_recipe_holds_no_credential_and_only_describes_local_paths_relatively():
    text = RECIPE_PATH.read_text()
    assert not TOKEN_PATTERN.search(text) and "Authorization" not in text and "Bearer" not in text
    assert "/home/" not in text and not Path(recipe()["adapter_config"]["remote_cache_root"]).is_absolute()


def test_snapshot_id_is_derived_from_the_pinned_shards_and_the_fixed_selection_and_never_from_a_budget():
    document = recipe()
    config = document["adapter_config"]
    lines = sorted(f"{entry['source_name']}:{entry['bytes']}:{entry['sha256']}" for entry in config["remote_files"])
    text = "\n".join(lines) + "\npreview_sampling:" + json.dumps(config["preview_sampling"], sort_keys=True)
    assert document["snapshot_id"] == f"bbq-v-{REVISION[:12]}-parquet45-{hashlib.sha256(text.encode()).hexdigest()[:16]}"
    assert not any("budget" in key or key.endswith("_bytes") for key in config["preview_sampling"])


def test_recipe_caps_keep_the_shards_remote_and_the_transfer_below_three_gigabytes():
    config = recipe()["adapter_config"]
    assert config["media_scope"] == "on_demand_unverified"  # no claim that every original was opened
    assert config["remote_cache_bytes"] <= 1_000_000_000
    assert config["media_transfer_bytes"] <= 250_000_000
    assert recipe()["expected_count"] == 54_414
    assert config["footer_workers"] <= 4  # modest concurrency against the Hub


def test_the_preview_selection_is_fixed_by_the_recipe_and_fits_the_caps_on_the_real_layout():
    sampling = recipe()["adapter_config"]["preview_sampling"]
    assert sampling == {"method": "sha256_ranked_row_groups_then_rows", "seed": 0, "row_groups": 40, "count": 100, "max_rows_per_group": 3}
    shards = receipt()["layout"]["shards"]
    # The receipt records the real row groups' sizes; the fixed selection over them must stay far below the transfer cap.
    from dataset_atlas.preparation.remote_sample import FixedRowGroupSampler
    groups = [(i, g["row_group"], g["rows"], g["bytes"]) for i, shard in enumerate(shards) for g in shard["row_group_sizes"]]
    sampler = FixedRowGroupSampler.from_spec(groups, [s["source_name"] for s in shards], sampling, byte_budget=4_000_000_000)
    assert sampler.selected_bytes == receipt()["preview"]["sampling"]["selected_row_group_transfer_bytes"] <= 1_200_000_000


# --- configuration, field types, and the absence of fabricated values ----------------------------------------------


def test_configuration_is_the_file_name_prefix_and_every_group_is_present(tmp_path, release):
    entries, *_ = release
    _, records = all_records(adapter_for(tmp_path, entries))
    by_group = {}
    for record in records:
        origin = record.source["_atlas_origin"]
        by_group.setdefault(record.source["_atlas_configuration"], set()).add(origin["file"])
        assert origin["file"].split("/")[-1].startswith(record.source["_atlas_configuration"] + "-")
    assert {group: len(files) for group, files in by_group.items()} == {group: spec[0] for group, spec in GROUPS.items()}
    assert len(records) == TOTAL_ROWS


def test_a_shard_name_that_matches_no_configuration_is_refused_not_guessed(tmp_path, release):
    entries, *_ = release
    entries = [{**entries[0], "source_name": "data/unnamed.parquet"}]
    adapter = adapter_for(tmp_path, entries)
    source = adapter.prepare(adapter.plan(5, 1_000_000))
    with pytest.raises(ValueError, match="configuration"):
        adapter.iter_records(source)


def test_a_pattern_and_a_path_rule_together_are_refused(tmp_path, release):
    entries, *_ = release
    adapter = adapter_for(tmp_path, entries, mapping={"configuration_from_path": True,
                                                      "configuration_pattern": recipe()["adapter_config"]["mapping"]["configuration_pattern"]})
    source = adapter.prepare(adapter.plan(5, 1_000_000))
    with pytest.raises(ValueError, match="one configuration rule"):
        adapter.iter_records(source)


def test_declared_class_codes_are_categories_with_the_authors_names_and_absent_labels_stay_absent(tmp_path, release):
    entries, *_ = release
    adapter = adapter_for(tmp_path, entries)
    declared = adapter.config["fields"]
    for field, names in CLASS_LABELS.items():
        assert declared[field]["dtype"] == "category"
        assert declared[field]["values"] == list(range(len(names)))
        # The mapping quoted in the description is the author's own ClassLabel list, in order.
        assert ", ".join(f"{code}={name}" for code, name in enumerate(names)) in declared[field]["description"]
    _, records = all_records(adapter)
    tests = [r for r in records if r.source["_atlas_configuration"] == "test"]
    answered = [r for r in records if r.source["_atlas_configuration"] != "test"]
    assert tests and all("label" not in r.source and "ans0" not in r.source for r in tests)
    assert answered and all(r.source["label"] in {0, 1, 2} and r.source["ans2"] == "unknown" for r in answered)
    assert adapter.source_field_types()["_atlas_configuration"] == "string"


def test_built_preview_exposes_the_declared_fields_with_numeric_values(tmp_path, release):
    from dataset_atlas.adapters import build_preview
    entries, *_ = release
    adapter = adapter_for(tmp_path, entries)
    pack = build_preview(adapter.dataset, tmp_path / "pack", adapter=adapter, limit=10, max_bytes=50_000_000)
    fields = {field.name: field for field in pack.fields}
    assert fields["category"].dtype == "category" and fields["category"].values == list(range(9))
    assert fields["question_polarity"].values == [0, 1] and fields["label"].values == [0, 1, 2]
    for record in pack.records:  # the source keeps a small descriptor of the image, never its bytes
        assert "bytes" not in record.source["file_name"] and len(json.dumps(record.source)) < 3_000


# --- the complete annotation index never reads image bytes ----------------------------------------------------------


def test_complete_index_covers_every_row_and_leaves_the_images_remote(tmp_path, release):
    entries, payloads, _, calls = release
    adapter = adapter_for(tmp_path, entries)
    source, records = all_records(adapter)
    assert adapter.count == len(records) == TOTAL_ROWS
    assert all(record.assets and record.assets[0].sha256 is None for record in records)
    # Only the annotation columns and footers were requested: far less than the shards hold.
    transferred = adapter.bytes_fetched
    assert 0 < transferred < sum(len(payload) for payload in payloads.values()) * 0.1
    assert adapter.media_bytes_fetched == 0
    image_chunks = []
    for entry in entries:
        metadata = pq.ParquetFile(io.BytesIO(payloads[entry["url"]])).metadata
        for group in range(metadata.num_row_groups):
            for column in range(metadata.row_group(group).num_columns):
                chunk = metadata.row_group(group).column(column)
                if chunk.path_in_schema == "file_name.bytes":
                    start = min(offset for offset in (chunk.dictionary_page_offset, chunk.data_page_offset) if offset is not None)
                    image_chunks.append((entry["url"], start, start + chunk.total_compressed_size))
    # The only read that may touch an image column is the 64 KB block holding each shard's footer, which can reach
    # back over the end of the last image chunk; no image chunk is ever requested as such.
    last_end = {url: max(end for u, _, end in image_chunks if u == url) for url in payloads}
    touching = [(url, offset, length) for url, offset, length in calls
                if any(url == u and offset < end and offset + length > start for u, start, end in image_chunks)]
    assert len(touching) <= len(entries)
    assert all(length <= 65_536 and offset + length >= last_end[url] for url, offset, length in touching)


def test_the_last_record_is_readable_through_the_ranged_route(tmp_path, release):
    entries, *_ = release
    adapter = adapter_for(tmp_path, entries)
    source = adapter.prepare(adapter.plan(5, 5_000_000))
    last = adapter.iter_records(source, str(TOTAL_ROWS - 1), 5)
    assert len(last.records) == 1 and last.next_cursor is None
    assert last.records[0].source["_atlas_origin"]["file"].endswith("test2-00000-of-00001.parquet")


# --- identity ---------------------------------------------------------------------------------------------------------


def test_record_ids_are_stable_across_page_sizes_order_and_a_fresh_mount(tmp_path, release):
    entries, *_ = release
    adapter = adapter_for(tmp_path, entries)
    source, streamed = all_records(adapter)
    ids = [record.id for record in streamed]
    assert len(set(ids)) == TOTAL_ROWS
    for page in (7, 33, 1000):
        paged, cursor = [], None
        while True:
            batch = adapter.iter_records(source, cursor, page)
            paged += batch.records
            cursor = batch.next_cursor
            if cursor is None:
                break
        assert [record.id for record in paged] == ids
        assert [asset.id for record in paged for asset in record.assets] == [a.id for r in streamed for a in r.assets]
    # A second adapter over the same pinned shards (a remount, with its own cache) produces the same identities.
    remount = adapter_for(tmp_path / "remount", entries)
    _, again = all_records(remount)
    assert [record.id for record in again] == ids
    # The sort order of a view does not matter: a row found by its position carries the same identity.
    by_id = {record.id: record for record in streamed}
    reordered = sorted(streamed, key=lambda r: (r.source["_atlas_origin"]["file"], -r.source["_atlas_origin"]["row"]))
    positions = []
    for record in reordered[:10]:
        origin = record.source["_atlas_origin"]
        file_index = [e["source_name"] for e in entries].index(origin["file"])
        positions.append((file_index, origin["row"] // 8, origin["row"] % 8))
    assert [r.id for r in adapter.records_at(source, positions)] == [r.id for r in reordered[:10]]
    assert all(by_id[r.id].source["_atlas_origin"] == r.source["_atlas_origin"] for r in reordered)


def test_upstream_ids_repeat_across_groups_never_within_one_and_every_row_is_kept(tmp_path, release):
    entries, *_ = release
    adapter = adapter_for(tmp_path, entries)
    source, records = all_records(adapter)
    assert adapter.validate(source, limit=TOTAL_ROWS).duplicate_source_ids == ()
    members = {}
    for record in records:
        members.setdefault(record.source["_atlas_configuration"], []).append(record.source["id"])
    for group, ids in members.items():
        assert len(ids) == len(set(ids)), group  # unique inside a group
    assert set(members["real"]) & set(members["test"])  # shared between groups, so source.id alone cannot identify a row
    assert len({record.id for record in records}) == TOTAL_ROWS == sum(len(ids) for ids in members.values())
    for record in records:
        assert record.source["id"] and record.source["_atlas_origin"]["upstream_sha256"]
        assert record.source["_atlas_origin"]["integrity"].startswith("Strong ETag-bound ranges")


def test_rows_that_share_an_image_name_keep_separate_assets(tmp_path, release):
    entries, *_ = release
    adapter = adapter_for(tmp_path, entries)
    source, records = all_records(adapter)
    shared = {}
    for record in records:
        if record.source["_atlas_configuration"] == "real":
            shared.setdefault(record.source["file_name"]["source_path"], []).append(record)
    repeated = [group for group in shared.values() if len(group) > 1]
    assert repeated
    for group in repeated:
        assert len({record.assets[0].id for record in group}) == len(group)  # one asset per row, not per file name
        assert len({record.id for record in group}) == len(group)
    group = repeated[0]
    assert len({adapter.resolve_asset(source, record.assets[0].uri).sha256 for record in group}) == 1  # same name, same bytes


# --- media ------------------------------------------------------------------------------------------------------------


def test_original_bytes_resolve_for_rows_beyond_the_first_hundred(tmp_path, release):
    entries, _, originals, _ = release
    adapter = adapter_for(tmp_path, entries)
    source, records = all_records(adapter)
    assert TOTAL_ROWS > 100
    late = [r for r in records if r.source["_atlas_configuration"] == "test2"][-1]
    handle = adapter.resolve_asset(source, late.assets[0].uri)
    expected = originals[f"test2-0-{late.source['_atlas_origin']['row']}"]
    assert handle.data == expected and handle.media_type == "image/jpeg"
    assert handle.sha256 == hashlib.sha256(expected).hexdigest()
    assert adapter.media_bytes_fetched > 0
    with Image.open(io.BytesIO(handle.data)) as image:
        assert image.size == Image.open(io.BytesIO(expected)).size  # the original, not a rendering


def test_missing_image_bytes_stay_visible_instead_of_being_filled_in(tmp_path, monkeypatch):
    def remove(group, shard, rows):
        if group == "real" and shard == 0:
            rows[1]["file_name"] = {"bytes": None, "path": "gone.jpg"}
            rows[2]["file_name"] = None

    entries, payloads, _ = write_release(tmp_path, mutate=remove)
    serve(monkeypatch, payloads)
    adapter = adapter_for(tmp_path, entries)
    source, records = all_records(adapter)
    assert len(records) == TOTAL_ROWS  # the rows are listed, never dropped
    real = [r for r in records if r.source["_atlas_origin"]["file"] == entries[0]["source_name"]]
    assert real[1].assets and real[1].source["file_name"]["source_path"] == "gone.jpg"
    with pytest.raises(FileNotFoundError, match="no embedded image bytes"):
        adapter.resolve_asset(source, real[1].assets[0].uri)
    assert real[2].assets == [] and real[2].source["file_name"] is None
    assert adapter.resolve_asset(source, real[0].assets[0].uri).data


def test_an_image_outside_the_declared_population_is_refused(tmp_path, release):
    entries, *_ = release
    adapter = adapter_for(tmp_path, entries)
    source = adapter.prepare(adapter.plan(5, 1_000_000))
    with pytest.raises(ValueError, match="outside"):
        adapter.resolve_asset(source, "remote/99/0/file_name/0.png")
    with pytest.raises(ValueError, match="outside"):
        adapter.resolve_asset(source, "remote/0/9999/file_name/0.png")


def test_a_row_group_beyond_the_media_budget_is_refused_not_truncated(tmp_path, release):
    entries, *_ = release
    adapter = adapter_for(tmp_path, entries, media_transfer_bytes=100)
    source = adapter.prepare(adapter.plan(1, 1_000_000))
    record = adapter.iter_records(source).records[0]
    with pytest.raises(ValueError, match="row group exceeds media transfer budget"):
        adapter.resolve_asset(source, record.assets[0].uri)


# --- failures ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_shard_says_why_and_what_to_do_and_never_leaks_the_token(tmp_path, monkeypatch, status):
    from urllib.parse import urlsplit

    class Response(io.BytesIO):
        def __init__(self):
            super().__init__(b"")
            self.status = status
            self.will_close = True

        def getheader(self, name, default=None):
            return {"Content-Length": "0"}.get(name, default)

    class Connection:
        def __init__(self, *args):
            pass

        def request(self, method, target, headers):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("dataset_atlas.storage.ranges._PinnedHTTPSConnection", Connection)
    monkeypatch.setattr("dataset_atlas.storage.https.HttpsFetcher._destination",
                        lambda self, url: (urlsplit(url).hostname, 443, "93.184.216.34", "/file"))
    monkeypatch.setenv("HF_TOKEN", "hf_fixture_only_never_printed")
    entry = {"source_name": "data/test-00000-of-00001.parquet", "bytes": 1000, "sha256": "a" * 64, "etag": '"x"',
             "url": f"https://huggingface.co/datasets/ucf-crcv/BBQ-V/resolve/{REVISION}/data/test-00000-of-00001.parquet"}
    adapter = adapter_for(tmp_path, [entry])
    source = adapter.prepare(adapter.plan(5, 1_000_000))
    with pytest.raises(ValueError) as refused:
        adapter.iter_records(source)  # a page of records is an error, never an empty page
    message = str(refused.value)
    assert f"HTTP {status}" in message and "terms" in message and "sign in" in message
    assert "hf_fixture_only_never_printed" not in message and "Bearer" not in message
    with pytest.raises(ValueError, match=f"HTTP {status}"):
        adapter.count


def test_exhausting_the_transfer_budget_stops_the_index_instead_of_truncating_it(tmp_path, release):
    entries, *_ = release
    adapter = adapter_for(tmp_path, entries, metadata_transfer_bytes=2_000)
    with pytest.raises(ValueError, match="budget"):
        adapter.warm_layouts()


# --- the whole preparation, end to end, on the synthetic release ----------------------------------------------------------

FIXTURE_TOKEN = "hf_fixture_private_token_value"
FIXTURE_SAMPLING = {"method": "sha256_ranked_row_groups_then_rows", "seed": 0, "row_groups": 20, "count": 100, "max_rows_per_group": 5}


def prepare_workspace(tmp_path, monkeypatch, name, budget=100_000_000):
    """An empty workspace holding only the catalogue entry and the real recipe, pointed at the synthetic shards."""
    import shutil
    from dataset_atlas.preparation import PreparationManager

    entries, payloads, originals = write_release(tmp_path / f"shards-{name}")
    root = tmp_path / name
    (root / "registry/datasets").mkdir(parents=True)
    (root / "registry/recipes").mkdir(parents=True)
    shutil.copy(ENTRY_PATH, root / "registry/datasets/sbbench.yaml")
    document = recipe()
    document["expected_count"] = TOTAL_ROWS
    document["adapter_config"]["remote_files"] = entries
    document["adapter_config"]["preview_sampling"] = FIXTURE_SAMPLING
    (root / "registry/recipes/sbbench.yaml").write_text(yaml.safe_dump(document, sort_keys=False))
    monkeypatch.setattr("dataset_atlas.storage.ranges.HttpsRangeReader._fetch", lambda self, start, end: payloads[self.url][start:end + 1])
    monkeypatch.setenv("HF_TOKEN", FIXTURE_TOKEN)
    manager = PreparationManager(root)
    plan = manager.plan("sbbench", budget, 100_000_000)
    return root, manager, plan, originals, payloads


def test_auto_planning_takes_the_complete_index_route_within_the_binding_caps(tmp_path, monkeypatch):
    root, manager, _, _, _ = prepare_workspace(tmp_path, monkeypatch, "auto")
    plan = manager.plan("sbbench", 1_300_000_000, 2_000_000_000, "auto")
    # A sampled route would skip the complete annotation index; this release must index every row.
    assert plan["ready"] and plan["kind"] == "local", plan["requirements"]
    assert plan["expected_download_bytes"] == plan["max_download_bytes"] == 1_300_000_000 and plan["download_is_upper_bound"]
    assert plan["max_output_bytes"] == 2_000_000_000 and plan["credential_profile"] == "huggingface"
    assert plan["resource_limits"]["max_wall_seconds"] >= 3600


def test_preparation_builds_the_complete_index_and_a_hundred_original_media_preview(tmp_path, monkeypatch):
    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry

    root, manager, plan, originals, payloads = prepare_workspace(tmp_path, monkeypatch, "first")
    assert plan["ready"], plan["requirements"]
    assert plan["credential_profile"] == "huggingface" and FIXTURE_TOKEN not in json.dumps(plan)
    run(root, plan["id"])
    assert manager.status(plan["id"])["status"] == "completed"
    registry = Registry(root)
    dataset = registry.dataset("sbbench")
    assert dataset.snapshot_id == recipe()["snapshot_id"] and dataset.release == recipe()["release"]
    assert dataset.adapter == "remote_columnar" and dataset.adapter_config["credential_profile"] == "huggingface"
    coverage = dataset.coverage
    assert (coverage.preview_count, coverage.total_count) == (100, TOTAL_ROWS)
    assert (coverage.adapter, coverage.preview, coverage.complete_data) == ("tested", "complete_target", "indexed_metadata_partial_media")
    assert coverage.access == "gated" and coverage.identity == "resolved" and coverage.publication == "not_reviewed"
    pack = registry.pack("sbbench")
    assert len(pack.records) == 100 and len({r.id for r in pack.records}) == 100
    assert pack.sampling["method"] == "sha256_ranked_row_groups_then_rows" and pack.sampling["seed"] == 0
    assert pack.sampling["population_count"] == TOTAL_ROWS and pack.sampling["returned_count"] == 100
    assert pack.sampling["grouping"] == "row group, then row within group" and pack.sampling["valid_for_population_prevalence"] is False
    assert pack.sampling["row_groups_selected"] == 20 and pack.sampling["row_groups_in_population"] == 24
    per_group = {}
    for record in pack.records:
        origin = record.source["_atlas_origin"]
        per_group.setdefault((origin["file"], origin["row"] // 8), []).append(origin["row"])
    assert len(per_group) == 20 and max(len(rows) for rows in per_group.values()) <= 5  # clustered by row group, a few rows each
    assert len({r.source["_atlas_configuration"] for r in pack.records}) >= 3
    version = registry.active_directory("sbbench")
    for record in pack.records:
        asset = record.assets[0]
        origin = record.source["_atlas_origin"]
        group, shard = re.search(r"data/([a-z0-9]+)-(\d{5})-of-", origin["file"]).groups()
        kept = (version / "pack" / asset.uri).read_bytes()
        assert kept == originals[f"{group}-{int(shard)}-{origin['row']}"]  # the original bytes, not a rendering
        assert hashlib.sha256(kept).hexdigest() == asset.sha256 == pack.checksums[asset.uri]
    rows = pq.read_table(registry.snapshot_path("sbbench") / "records.parquet", columns=["record_json"]).column(0).to_pylist()
    ids = [json.loads(value)["id"] for value in rows]
    assert len(ids) == len(set(ids)) == TOTAL_ROWS
    receipt = json.loads((version / "receipt.json").read_text())
    assert receipt["snapshot_id"] == recipe()["snapshot_id"] and receipt["record_count"] == TOTAL_ROWS
    # The index read annotation columns and footers only; images moved only for the sampled rows.
    assert 0 < receipt["remote_metadata_bytes"] < sum(len(data) for data in payloads.values()) * 0.2
    assert receipt["total_transfer_bytes"] == receipt["remote_metadata_bytes"] + receipt["remote_media_bytes"]
    assert receipt["retained_preview_original_bytes"] > 0 and receipt["remote_media_bytes"] > 0
    # The credential is resolved at read time and never reaches a plan, a receipt, a pack or a prepared dataset file.
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".yaml", ".jsonl", ".txt"}:
            assert FIXTURE_TOKEN not in path.read_text(errors="replace"), path.name


def test_an_empty_workspace_prepares_the_same_snapshot_and_the_same_preview(tmp_path, monkeypatch):
    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry

    seen = []
    for name in ("maintainer", "colleague"):
        root, manager, plan, _, _ = prepare_workspace(tmp_path, monkeypatch, name)
        run(root, plan["id"])
        registry = Registry(root)
        pack = registry.pack("sbbench")
        seen.append((registry.dataset("sbbench").snapshot_id, [r.id for r in pack.records], pack.sampling["rows_drawn"],
                     [hashlib.sha256((registry.active_directory("sbbench") / "pack" / r.assets[0].uri).read_bytes()).hexdigest() for r in pack.records]))
    assert seen[0] == seen[1]


def test_the_transfer_budget_never_changes_which_records_the_preview_holds(tmp_path, monkeypatch):
    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry

    chosen = []
    for name, budget in (("tight", 30_000_000), ("generous", 400_000_000)):
        root, manager, plan, _, _ = prepare_workspace(tmp_path, monkeypatch, name, budget)
        assert plan["ready"], plan["requirements"]
        run(root, plan["id"])
        registry = Registry(root)
        pack = registry.pack("sbbench")
        chosen.append((registry.dataset("sbbench").snapshot_id, [r.id for r in pack.records], pack.sampling["selected_row_groups"]))
    assert chosen[0] == chosen[1]


def test_a_budget_that_cannot_admit_the_fixed_selection_refuses_the_run_and_leaves_nothing_behind(tmp_path, monkeypatch):
    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry

    root, manager, plan, _, payloads = prepare_workspace(tmp_path, monkeypatch, "refused", budget=1_500_000)
    with pytest.raises(ValueError, match="does not change with the budget"):
        run(root, plan["id"])
    assert manager.status(plan["id"])["status"] == "failed"
    assert Registry(root).active_directory("sbbench") is None


# --- the registry entry, the receipt and the recipe agree --------------------------------------------------------------


def entry() -> dict:
    return yaml.safe_load(ENTRY_PATH.read_text())


def test_entry_coverage_states_each_dimension_separately_and_keeps_the_limits():
    coverage = entry()["coverage"]
    assert coverage["identity"] == "resolved" and coverage["source"] == "verified"
    assert coverage["access"] == "gated"  # the terms are the researcher's own; the entry stays gated
    assert coverage["adapter"] == "tested" and coverage["preview"] == "complete_target"
    assert coverage["preview_count"] == 100 and coverage["unit"] == "example"
    assert coverage["complete_data"] == "indexed_metadata_partial_media"
    assert coverage["total_count"] == 54_414
    assert coverage["publication"] == "not_reviewed"
    blockers = " ".join(coverage["blockers"])
    assert "historical SBBench population differ" in blockers  # the paper-population limit is kept
    assert "Adapter and preview are not implemented" not in blockers
    assert "Access approval is not present" not in blockers
    assert any("2026-10-08" in b and "terms" in b for b in coverage["blockers"])
    assert entry()["rights"]["images"] == "not_reviewed" and entry()["release"] == recipe()["release"]
    assert entry()["adapter"] == "remote_columnar" and entry()["adapter_config"] == {}


def git_show(path: str):
    try:
        return subprocess.run(["git", "show", f"{BASE_COMMIT}:{path}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def test_earlier_evidence_is_untouched_and_the_new_items_cite_the_receipt():
    old = git_show("registry/datasets/sbbench.yaml")
    if old is None:
        pytest.skip("base commit is not available in this checkout")
    before, now = yaml.safe_load(old), entry()
    assert now["evidence"][:len(before["evidence"])] == before["evidence"]
    added = now["evidence"][len(before["evidence"]):]
    assert [item["kind"] for item in added] == ["source_audit_access", "native_population_live_verification"]
    access, verification = added
    assert access["checked_on"] == "2026-10-08" and "accepted the terms" in access["note"]
    assert access["audit_file"] == verification["receipt"] == "reports/bbq-v-live-verification-20261008.json"
    assert "historical" in verification["source_identity_status"]
    for field in ("identity", "paper_ids", "rights", "aliases", "source_url", "relationships"):
        assert now.get(field) == before.get(field), field
    assert not TOKEN_PATTERN.search(ENTRY_PATH.read_text())


def receipt() -> dict:
    return json.loads(RECEIPT_PATH.read_text())


def test_receipt_holds_no_credential_and_no_local_path():
    text = RECEIPT_PATH.read_text()
    assert not TOKEN_PATTERN.search(text)
    assert not re.search(r"authorization|bearer", text, re.IGNORECASE)
    assert "/home/" not in text and "/tmp/" not in text


def test_receipt_respects_the_binding_caps_and_measures_what_moved():
    document = receipt()
    transfer = document["bytes_transferred"]
    assert transfer["total_measured_bytes"] <= 3_000_000_000 == document["caps"]["transfer_bytes"]
    assert document["prepared_output"]["bytes"] <= 2_000_000_000 == document["caps"]["prepared_output_bytes"]
    assert transfer["total_measured_bytes"] == sum(part["bytes"] for part in transfer["parts"].values())
    assert document["shards_downloaded_whole"] == 0 and document["token_in_receipt"] is False
    assert document["repository_downloaded_whole"] is False


def test_receipt_lists_the_same_shards_as_the_recipe_with_footer_row_counts():
    document, files = receipt(), recipe()["adapter_config"]["remote_files"]
    shards = document["layout"]["shards"]
    assert [(s["source_name"], s["bytes"], s["sha256"], s["etag"]) for s in shards] == \
           [(f["source_name"], f["bytes"], f["sha256"], f["etag"]) for f in files]
    assert sum(s["rows"] for s in shards) == recipe()["expected_count"] == document["layout"]["total_rows"]
    assert document["source"]["revision"] == REVISION
    groups = document["layout"]["groups"]
    assert sum(group["rows"] for group in groups.values()) == recipe()["expected_count"]
    assert {name: group["shards"] for name, group in groups.items()} == {"real": 7, "synthetic": 20, "test": 10, "test2": 8}


def test_receipt_class_labels_match_the_recipes_declared_fields():
    declared = recipe()["adapter_config"]["fields"]
    for field, names in receipt()["schema"]["class_labels"].items():
        assert declared[field]["values"] == list(range(len(names)))
        assert ", ".join(f"{code}={name}" for code, name in enumerate(names)) in declared[field]["description"]
    assert receipt()["schema"]["class_labels_agree_in_every_shard_that_has_the_column"] is True


def test_receipt_records_the_preview_the_sampling_and_the_beyond_row_hundred_reads():
    document = receipt()
    preview = document["preview"]
    assert preview["records"] == 100 and preview["snapshot_id"] == recipe()["snapshot_id"]
    sampling = preview["sampling"]
    assert sampling["seed"] == 0 and sampling["method"] and sampling["population_count"] == recipe()["expected_count"]
    assert preview["original_media"]["verified"] == 100 and preview["original_media"]["representation"] == "original"
    live = document["live_reads"]
    assert live["last_record"]["row_index"] == recipe()["expected_count"] - 1
    assert live["beyond_row_100"]["original_bytes_verified"] >= 1
    assert document["index"]["records"] == recipe()["expected_count"]
    assert document["index"]["unique_record_ids"] == recipe()["expected_count"]
