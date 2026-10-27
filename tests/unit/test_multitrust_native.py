"""MultiTrust (thu-ml/MultiTrust, catalogue entry `multitrust`) through the native `multitrust` adapter.

Every query file and every image in this file is SYNTHETIC: it copies only the layouts of the gated release (a JSON array, JSON
Lines saved under a `.json` name, CSV, plain text lines with a companion label file, JSON objects of lists and of objects, derived
image names, ordinal pairings, a task whose images are paired at run time). No gated content is copied into the repository. Current source pins and declared native-unit counts are checked from the shipped recipe and catalogue evidence.
Historical verification receipts remain in the private recovery archive, outside these behavioral tests.
"""
from __future__ import annotations

import hashlib
import io
import json
import random
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

import pytest
import yaml
from PIL import Image

from dataset_atlas.adapters import get_adapter
from dataset_atlas.adapters.multitrust import MultiTrustAdapter
from dataset_atlas.models import Dataset

ROOT = Path(__file__).resolve().parents[2]
RECIPE_PATH = ROOT / "registry/recipes/multitrust.yaml"
ENTRY_PATH = ROOT / "registry/datasets/multitrust.yaml"
MEDIA_PATH = ROOT / "registry/media/multitrust.json"
REVISION = "84dc74754959e9f52b67c5185700f4f7fcd8c4df"
BASE_URL = f"https://huggingface.co/datasets/thu-ml/MultiTrust/resolve/{REVISION}"
TOKEN_PATTERN = re.compile(r"hf_[A-Za-z0-9]{20,}")
FIXTURE_TOKEN = "hf_fixture_private_token_value"
ASPECTS = ["truthfulness", "safety", "robustness", "fairness", "privacy"]


def recipe() -> dict:
    return yaml.safe_load(RECIPE_PATH.read_text())


# --- a synthetic release in the real layouts ---------------------------------------------------------------------------


def png(seed: int) -> bytes:
    buffer = io.BytesIO()
    Image.frombytes("RGB", (16, 16), random.Random(seed).randbytes(16 * 16 * 3)).save(buffer, "PNG")
    return buffer.getvalue()


def md5(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


def lines(*items) -> bytes:
    return ("\n".join(items) + "\n").encode()


def dump(value) -> bytes:
    return json.dumps(value).encode()


def csv_bytes(header: list[str], rows: list[list]) -> bytes:
    return lines(",".join(header), *[",".join(str(cell) for cell in row) for row in rows])


def img(template, role=None, **extra):
    return {"template": template, **({"role": role} if role else {}), **extra}


def task(name, aspect, fmt, query_file=None, media=(), basis="key_in_query_row", **extra):
    return {"task": name, "aspect": aspect, "format": fmt, **({"query_file": query_file} if query_file else {}), **extra,
            "media": list(media), "join_basis": basis, "toolkit_tasks": []}


class Release:
    """Query files, images and the inventory of a synthetic suite, plus the counts the layout implies."""

    def __init__(self):
        self.queries: dict[str, bytes] = {}
        self.images: dict[str, bytes] = {}
        self.tasks: list[dict] = []
        self.rows_by_task: dict[str, int] = {}
        self._seed = 0

    def image(self, path: str) -> None:
        self._seed += 1
        self.images[path] = png(self._seed)

    def build(self) -> "Release":
        # truthfulness: a JSON array; the last three rows name images that the release does not hold
        rows = [{"id": i, "image": f"{i % 10 + 1}.png", "query": f"synthetic question {i}", "truth": "yes"} for i in range(27)]
        rows += [{"id": 27 + i, "image": f"{90 + i}.png", "query": "synthetic question", "truth": "no"} for i in range(3)]
        self.queries["truthfulness/query_basic/q_a.json"] = dump(rows)
        for number in range(1, 11):
            self.image(f"truthfulness/basic_images/a/{number}.png")
        self.tasks.append(task("basic_a", "truthfulness", "json", "truthfulness/query_basic/q_a.json", [img("truthfulness/basic_images/a/{image}")]))
        self.rows_by_task["basic_a"] = 30
        # safety: a CSV with an image column, a CSV whose rows are paired with a pool at run time (no image), and an object of
        # string lists whose image name is the category plus the MD5 of the text
        self.queries["safety/s.csv"] = csv_bytes(["id", "question", "image_path"], [[i, f"synthetic {i}", f"p{i}.png"] for i in range(20)])
        for i in range(20):
            self.image(f"safety/s/p{i}.png")
        self.tasks.append(task("s_csv", "safety", "csv", "safety/s.csv", [img("safety/s/{image_path}")]))
        self.rows_by_task["s_csv"] = 20
        self.queries["safety/c.csv"] = csv_bytes(["id", "question", "jailbreak"], [[i, f"synthetic {i}", "x"] for i in range(6)])
        for i in range(2):
            self.image(f"safety/pool/{i}.png")
        self.tasks.append(task("s_pool", "safety", "csv", "safety/c.csv", [], "none_cross_product_in_toolkit"))
        self.rows_by_task["s_pool"] = 6
        groups = {"cat1": [f"synthetic cat1 {i}" for i in range(8)], "cat2": [f"synthetic cat2 {i}" for i in range(8)]}
        self.queries["safety/prompts.json"] = dump(groups)
        for name, items in groups.items():
            for text in items:
                self.image(f"safety/rtp/images/{name}_{md5(text)}.png")
        for i in range(5):
            self.image(f"safety/rtp/images/cat3_{i:032x}.png")  # images no row names
        self.tasks.append(task("s_groups", "safety", "json_groups", "safety/prompts.json",
                               [img("safety/rtp/images/{_group}_{prompt|md5}.png")], "derived_key", group_field="category", string_item_field="prompt"))
        self.rows_by_task["s_groups"] = 16
        # robustness: an object of lists of objects (image named by category and idx) and several JSON Lines files
        lab = {"g1": [{"idx": i, "sentence": f"synthetic {i}", "label": 1} for i in range(10)],
               "g2": [{"idx": 100 + i, "sentence": f"synthetic {i}", "label": 0} for i in range(10)]}
        self.queries["robustness/lab.json"] = dump(lab)
        for group, items in lab.items():
            for item in items:
                self.image(f"robustness/lab/related/{group}/{item['idx']}.png")
        self.tasks.append(task("r_lab", "robustness", "json_groups", "robustness/lab.json", [img("robustness/lab/related/{_group}/{idx}.png")],
                               "derived_key", group_field="category"))
        self.rows_by_task["r_lab"] = 20
        files = []
        for stem in ("a", "b"):
            name = f"robustness/sens/label/{stem}.json"
            files.append(name)
            self.queries[name] = lines(*[json.dumps({"image_id": i, "image_name": f"{stem.upper()}/{i}.png", "question": "q", "answer": "a"}) for i in range(8)])
            for i in range(8):
                self.image(f"robustness/sens/source/{stem.upper()}/{i}.png")
        self.tasks.append(task("r_sens", "robustness", "jsonl", None, [img("robustness/sens/source/{image_name}")], query_files=files))
        self.rows_by_task["r_sens"] = 16
        # fairness: a derived lower-cased folder, and ordinal pairings (the vision image for the first twelve rows, two candidates for all)
        self.queries["fairness/st.csv"] = csv_bytes(["Number", "Stereo Statement", "Type"], [[n, f"synthetic {t} {n}", t] for t in ("Age", "Race") for n in range(1, 7)])
        for folder in ("age", "race"):
            for n in range(1, 7):
                self.image(f"fairness/stereo/{folder}/{n}.png")
        self.tasks.append(task("f_stmt", "fairness", "csv", "fairness/st.csv", [img("fairness/stereo/{Type|lower}/{Number}.png")], "derived_key"))
        self.rows_by_task["f_stmt"] = 12
        self.queries["fairness/pref.json"] = dump([{"prompt": f"synthetic {i}", "topic": "t", "type": "plain" if i < 12 else "force"} for i in range(24)])
        for n in range(1, 13):
            for folder in ("vis", "a", "b"):
                self.image(f"fairness/{folder}/{n}.png")
        self.tasks.append(task("f_pref", "fairness", "json", "fairness/pref.json",
                               [img("fairness/vis/{_row}.png", "vision", row_lt=12), img("fairness/a/{_row_mod1}.png", "a"), img("fairness/b/{_row_mod1}.png", "b")],
                               "ordinal_in_toolkit_loader", row_modulo=12))
        self.rows_by_task["f_pref"] = 24
        # privacy: text lines with a shorter label file and an image per row modulo four, a keyed object, and an underscored name
        self.queries["privacy/prompts.txt"] = lines(*[f"synthetic prompt {i}" for i in range(10)])
        self.queries["privacy/labels.txt"] = lines(*[str(i) for i in range(9)])
        for n in range(4):
            self.image(f"privacy/imgs/{n}.png")
        self.tasks.append(task("p_lines", "privacy", "text_lines", "privacy/prompts.txt", [img("privacy/imgs/{_row_mod}.png")], "ordinal_in_toolkit_loader",
                               row_modulo=4, companion_lines={"source_name": "privacy/labels.txt", "field": "label"}))
        self.rows_by_task["p_lines"] = 10
        self.queries["privacy/keyed.json"] = dump({str(i): {"ID": i, "Image": f"a/{i}.png", "Question": "q"} for i in range(1, 7)})
        for i in range(1, 7):
            self.image(f"privacy/k/a/{i}.png")
        self.tasks.append(task("p_keyed", "privacy", "json_keyed", "privacy/keyed.json", [img("privacy/k/{Image}")], key_field="_key"))
        self.rows_by_task["p_keyed"] = 6
        self.queries["privacy/celeb.csv"] = csv_bytes(["Celebrity", "Title", "Url"], [["Ana Lee", "t", "https://example.invalid/x"] for _ in range(2)] +
                                                   [[f"Bo Kim{i}", "t", "https://example.invalid/y"] for i in range(3)])
        for name in ("Ana_Lee", "Bo_Kim0", "Bo_Kim1", "Bo_Kim2"):
            self.image(f"privacy/celeb/imgs/{name}.jpeg")
        self.tasks.append(task("p_celeb", "privacy", "csv", "privacy/celeb.csv", [img("privacy/celeb/imgs/{Celebrity|underscore}.jpeg")], "derived_key"))
        self.rows_by_task["p_celeb"] = 5
        # a file of the release that no query names (a font-like non-image is not in the image inventory)
        self.image("unrelated_images/1_c.png")
        return self

    # counts the layout implies, written down independently of the adapter
    TOTAL_ROWS = 30 + 20 + 6 + 16 + 20 + 16 + 12 + 24 + 10 + 6 + 5
    ROWS_WITHOUT_IMAGE_BY_DESIGN = 6
    ABSENT_REFERENCES = 3
    ROWS_BY_ASPECT = {"truthfulness": 30, "safety": 42, "robustness": 36, "fairness": 36, "privacy": 21}

    def inventory(self) -> dict:
        files = {}
        for path, data in sorted(self.images.items()):
            entry = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            if path == "safety/s/p0.png":  # a file the Hub holds without an LFS hash is pinned by its Git blob SHA-1
                entry = {"bytes": len(data), "git_blob_sha1": hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()}
            files[path] = entry
        return {"files": files}

    def payloads(self) -> dict[str, bytes]:
        return {f"{BASE_URL}/{quote(name, safe='/')}": data for name, data in {**self.queries, **self.images}.items()}


def dataset_for(tmp_path: Path, release: Release, **config) -> Dataset:
    """The dataset configured exactly as the real recipe configures it, over the synthetic suite."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    media = tmp_path / "media-inventory.json"
    media.write_text(json.dumps(release.inventory(), separators=(",", ":"), sort_keys=True))
    options = {key: value for key, value in recipe()["adapter_config"].items()
               if key not in {"tasks", "inventory_tasks", "media_inventory_path", "remote_cache_root"}}
    files = []
    for name, data in release.queries.items():
        target = tmp_path / "queries" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append({"source_name": name, "path": str(target), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    options.update(tasks=release.tasks, source_files=files, media_inventory_path=str(media), remote_cache_root=str(tmp_path / "cache"),
                   media_inventory_sha256=hashlib.sha256(media.read_bytes()).hexdigest(), **config)
    entry = yaml.safe_load(ENTRY_PATH.read_text())
    entry.update(adapter="multitrust", adapter_config=options, release=f"multitrust-{REVISION}", snapshot_id="multitrust-fixture")
    return Dataset.model_validate(entry)


@pytest.fixture
def release() -> Release:
    return Release().build()


def adapter_for(tmp_path, release, **config) -> MultiTrustAdapter:
    return get_adapter(dataset_for(tmp_path, release, **config))


def all_records(adapter, page=1000):
    source = adapter.prepare(adapter.plan(100, 10_000_000_000))
    cursor, out = None, []
    while True:
        batch = adapter.iter_records(source, cursor, page)
        out.extend(batch.records)
        if not batch.next_cursor:
            return out, source
        cursor = batch.next_cursor


class FakeHub:
    """Answers every fetch from memory and records each as (url, credential profile). Counts transferred bytes like the real fetcher."""

    def __init__(self, monkeypatch, payloads: dict[str, bytes]):
        self.payloads, self.calls, self.fetched = payloads, [], 0
        hub = self

        def fetch(fetcher, url, cache, identity, *, expected_sha256=None, byte_budget=None, cancel=None, progress=None):
            cached = cache.get(identity)
            if cached:
                return cached
            data = hub.payloads[url]
            limit = min(fetcher.max_bytes, cache.max_bytes, byte_budget if byte_budget is not None else fetcher.max_bytes)
            if len(data) > limit:
                raise ValueError("Content-Length exceeds fetch budget")
            hub.calls.append((url, fetcher.credential_profile))
            fetcher.bytes_fetched += len(data)
            hub.fetched += len(data)
            partial = cache.partial_path(identity)
            partial.write_bytes(data)
            return cache.commit(identity, partial, fingerprint_type="none", fingerprint=None, expected_sha256=expected_sha256)

        monkeypatch.setattr("dataset_atlas.storage.https.HttpsFetcher.fetch", fetch)


# --- the recipe ---------------------------------------------------------------------------------------------------------


def test_recipe_pins_every_query_file_at_one_revision_and_names_the_credential_profile():
    document = recipe()
    assert document["adapter"] == "multitrust" and document["credential_profile"] == "huggingface"
    assert document["adapter_config"]["credential_profile"] == "huggingface"
    assert "source_url" not in document  # a huggingface.co/datasets URL would route to the sampled preview, which builds no index
    assert document["release"] == f"multitrust-{REVISION}" and document["adapter_config"]["media_base_url"] == BASE_URL
    for entry in document["files"]:
        assert entry["url"] == f"{BASE_URL}/{quote(entry['source_name'], safe='/')}"
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) and type(entry["bytes"]) is int and entry["bytes"] > 0
    names = [entry["source_name"] for entry in document["files"]]
    assert len(names) == len(set(names))
    used = set()
    for item in document["adapter_config"]["tasks"]:
        used.update(item.get("query_files") or [item["query_file"]])
        if item.get("companion_lines"):
            used.add(item["companion_lines"]["source_name"])
    assert used == set(names)  # every pinned file is a query file some task reads, and every task file is pinned


def test_recipe_holds_no_credential_and_only_describes_local_paths_relatively():
    text = RECIPE_PATH.read_text()
    assert not TOKEN_PATTERN.search(text) and not re.search(r"bearer|authorization", text, re.IGNORECASE)
    assert "/home/" not in text and "/tmp/" not in text
    config = recipe()["adapter_config"]
    assert not Path(config["media_inventory_path"]).is_absolute() and not Path(config["remote_cache_root"]).is_absolute()


def canon(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_snapshot_id_is_derived_from_the_pins_the_task_table_and_the_fixed_selection_and_never_from_a_budget():
    document = recipe()
    config = document["adapter_config"]
    media_sha = hashlib.sha256(MEDIA_PATH.read_bytes()).hexdigest()
    assert config["media_inventory_sha256"] == media_sha
    parts = sorted(f"{f['source_name']}:{f['bytes']}:{f['sha256']}" for f in document["files"])
    parts += [f"media_inventory:{media_sha}", f"tasks:{hashlib.sha256(canon(config['tasks']).encode()).hexdigest()}",
              f"inventory_tasks:{hashlib.sha256(canon(config['inventory_tasks']).encode()).hexdigest()}",
              f"preview_sampling:{canon(config['preview_sampling'])}"]
    digest = hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]
    assert document["snapshot_id"] == f"multitrust-{REVISION[:12]}-q{len(document['files'])}-{digest}"
    assert not re.search(r"budget|bytes", document["snapshot_id"])
    assert config["preview_sampling"] == {"method": "sha256_bottom_k_primary_asset_verified_media", "seed": 0, "candidate_pool": 250, "count": 100,
                                          "stratify_by": {"field": "aspect", "values": ["truthfulness", "safety", "robustness", "fairness", "privacy", "shared"]}}


def test_recipe_caps_keep_the_images_remote_and_declare_an_upper_bound_below_three_gigabytes():
    document, config = recipe(), recipe()["adapter_config"]
    pinned = sum(entry["bytes"] for entry in document["files"])
    assert pinned < 10_000_000  # query files are small text; no image is a pinned download
    assert document["preview_media_transfer_bytes"] > 0
    assert pinned + document["preview_media_transfer_bytes"] <= 3_000_000_000
    assert config["remote_cache_bytes"] <= 1_000_000_000 and config["verify_remote_preview_media"] is True
    assert config["preview_group_by"] == "primary_asset" and config["media_scope"] == "partial"
    assert not any(entry["source_name"].lower().endswith((".png", ".jpg", ".jpeg", ".gif")) for entry in document["files"])


def test_media_inventory_pins_every_image_by_a_content_hash():
    inventory = json.loads(MEDIA_PATH.read_text())["files"]
    assert len(inventory) == 10_464
    assert not any(path.startswith("/") or ".." in path.split("/") for path in inventory)
    without_lfs = [path for path, entry in inventory.items() if "sha256" not in entry]
    assert without_lfs == ["privacy/vispr/test2017/2017_51479450.1"]
    for entry in inventory.values():
        assert type(entry["bytes"]) is int and 1 <= entry["bytes"] <= 250_000_000
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) if "sha256" in entry else re.fullmatch(r"[0-9a-f]{40}", entry["git_blob_sha1"])
    assert not TOKEN_PATTERN.search(MEDIA_PATH.read_text())


def test_shipped_task_table_declares_query_and_inventory_tasks():
    document = recipe()
    tasks = document["adapter_config"]["tasks"]
    assert len(tasks) == len({item["task"] for item in tasks}) == 50
    assert {item["aspect"] for item in tasks} == set(ASPECTS)
    fields = recipe()["adapter_config"]["fields"]
    assert fields["task"]["dtype"] == fields["aspect"]["dtype"] == "category"
    assert fields["task"]["values"] == list(dict.fromkeys(item["task"] for item in tasks + recipe()["adapter_config"]["inventory_tasks"]))
    assert fields["aspect"]["values"] == ASPECTS + ["shared"]
    for item in tasks:
        assert item["format"] in {"json", "jsonl", "csv", "text_lines", "json_groups", "json_keyed"}
        assert item["join_basis"] in {"key_in_query_row", "derived_key", "ordinal_in_toolkit_loader",
                                      "none_cross_product_in_toolkit", "none_listdir_order_in_toolkit"}
        if not item["media"]:
            assert item["join_basis"].startswith("none_")


# --- the adapter on the synthetic suite ---------------------------------------------------------------------------------


def test_the_adapter_is_registered_under_its_catalogue_name(tmp_path, release):
    assert isinstance(adapter_for(tmp_path, release), MultiTrustAdapter)


def test_one_record_per_query_row_with_task_aspect_and_native_fields(tmp_path, release):
    records, _ = all_records(adapter_for(tmp_path, release))
    assert len(records) == release.TOTAL_ROWS == len({r.id for r in records})
    by_aspect = {}
    for record in records:
        by_aspect[record.source["aspect"]] = by_aspect.get(record.source["aspect"], 0) + 1
        origin = record.source["_atlas_origin"]
        assert origin["split"] == record.source["task"] and origin["file"] == record.source["query_file"]
        assert origin["identity"].startswith(record.source["task"] + ":") and type(origin["row"]) is int
    assert by_aspect == release.ROWS_BY_ASPECT and set(by_aspect) == set(ASPECTS)
    first = next(r for r in records if r.source["task"] == "basic_a")
    assert first.source["query"] == "synthetic question 0" and first.source["id"] == 0  # native fields are kept as they are
    assert first.source["_atlas_origin"] == {"split": "basic_a", "row": 0, "file": "truthfulness/query_basic/q_a.json",
                                              "identity": "basic_a:0", "group": "truthfulness"}


def test_record_ids_are_stable_across_page_sizes_and_a_fresh_adapter(tmp_path, release):
    one = [r.id for r in all_records(adapter_for(tmp_path / "one", release), page=1000)[0]]
    paged = [r.id for r in all_records(adapter_for(tmp_path / "paged", release), page=7)[0]]
    assert one == paged and len(set(one)) == len(one)
    shuffled = Release().build()
    shuffled.tasks.reverse()  # the id of a row depends on its task and position in the query file, not on the order of tasks
    reordered = {r.source["_atlas_origin"]["identity"]: r.id for r in all_records(adapter_for(tmp_path / "re", shuffled))[0]}
    assert reordered == {r.source["_atlas_origin"]["identity"]: r.id for r in all_records(adapter_for(tmp_path / "base", release))[0]}


def test_every_join_is_counted_and_nothing_is_dropped(tmp_path, release):
    adapter = adapter_for(tmp_path, release)
    report = adapter.join_report()
    assert report["rows"] == release.TOTAL_ROWS == adapter.count
    tasks = report["tasks"]
    assert {name: stats["rows"] for name, stats in tasks.items()} == release.rows_by_task
    assert sum(s["rows_without_image_reference"] for s in tasks.values()) == release.ROWS_WITHOUT_IMAGE_BY_DESIGN
    assert tasks["s_pool"]["join_basis"] == "none_cross_product_in_toolkit" and tasks["s_pool"]["rows_with_image_reference"] == 0
    assert sum(s["references_absent"] for s in tasks.values()) == release.ABSENT_REFERENCES == len(report["absent_image_paths"])
    assert tasks["basic_a"]["rows_with_absent_image"] == 3 and tasks["basic_a"]["references_present"] == 27
    assert tasks["f_pref"]["image_references"] == 12 + 24 + 24  # the vision image for twelve rows, two candidates for all
    assert tasks["s_groups"]["references_present"] == 16 and tasks["p_celeb"]["references_present"] == 5
    # an image named by no row is counted, never ignored: five RTP-style extras, the pool images and the unrelated image
    unreferenced = report["inventory_images_without_a_query_row"]
    assert sum(path.startswith("safety/rtp/images/cat3_") for path in unreferenced) == 5
    assert "unrelated_images/1_c.png" in unreferenced and "safety/pool/0.png" in unreferenced
    assert report["inventory_images"] == len(release.images) == report["referenced_inventory_images"] + len(unreferenced)


def test_derived_and_ordinal_image_names_follow_the_authors_loaders(tmp_path, release):
    records, _ = all_records(adapter_for(tmp_path, release))
    refs = {r.source["_atlas_origin"]["identity"]: [a.uri for a in r.assets] for r in records}
    text = "synthetic cat2 3"
    assert refs["s_groups:3"] == [f"file/safety/rtp/images/cat1_{md5('synthetic cat1 3')}.png"]
    assert refs["s_groups:11"] == [f"file/safety/rtp/images/cat2_{md5(text)}.png"]
    assert refs["r_lab:15"] == ["file/robustness/lab/related/g2/105.png"]
    assert refs["r_sens:b:2"] == ["file/robustness/sens/source/B/2.png"]
    assert refs["f_stmt:7"] == ["file/fairness/stereo/race/2.png"]
    assert refs["f_pref:3"] == ["file/fairness/vis/4.png", "file/fairness/a/4.png", "file/fairness/b/4.png"]
    assert refs["f_pref:15"] == ["file/fairness/a/4.png", "file/fairness/b/4.png"]  # no vision image beyond the first twelve rows
    assert refs["p_lines:6"] == ["file/privacy/imgs/2.png"] and refs["p_celeb:0"] == refs["p_celeb:1"] == ["file/privacy/celeb/imgs/Ana_Lee.jpeg"]
    assert refs["p_keyed:2"] == ["file/privacy/k/a/3.png"] and refs["s_pool:0"] == []
    roles = next(r for r in records if r.source["_atlas_origin"]["identity"] == "f_pref:3").assets
    assert [a.metadata["role"] for a in roles] == ["vision", "a", "b"]


def test_text_lines_keep_every_prompt_and_leave_a_missing_label_absent(tmp_path, release):
    records, _ = all_records(adapter_for(tmp_path, release))
    lines_ = [r for r in records if r.source["task"] == "p_lines"]
    assert len(lines_) == 10 and [r.source["label"] for r in lines_][-2:] == ["8", None]  # ten prompts, nine labels
    keyed = [r for r in records if r.source["task"] == "p_keyed"]
    assert [r.source["_key"] for r in keyed] == ["1", "2", "3", "4", "5", "6"]


def test_missing_image_references_stay_visible_as_absent_assets(tmp_path, release):
    adapter = adapter_for(tmp_path, release)
    records, source = all_records(adapter)
    absent = [r for r in records if r.source["task"] == "basic_a" and r.source["id"] >= 27]
    assert len(absent) == 3
    for record in absent:
        (asset,) = record.assets
        assert asset.uri is None and asset.metadata["availability"] == "absent_from_pinned_release"
        assert asset.metadata["source_path"] == f"file/truthfulness/basic_images/a/{record.source['image']}"
    report = adapter.validate_media(1_000_000)
    assert report["absent_media_references"] == 3 and report["metadata_bytes_fetched"] == 0 and report["rows"] == release.TOTAL_ROWS
    assert report["rows_without_image_reference"] == release.ROWS_WITHOUT_IMAGE_BY_DESIGN
    with pytest.raises(ValueError, match="absent from pinned inventory"):
        adapter.resolve_asset(source, "file/truthfulness/basic_images/a/90.png")


def test_an_image_outside_the_pinned_inventory_is_refused(tmp_path, release):
    adapter = adapter_for(tmp_path, release)
    _, source = all_records(adapter)
    with pytest.raises(ValueError, match="absent from pinned inventory"):
        adapter.resolve_asset(source, "file/not/in/the/release.png")
    with pytest.raises(ValueError):
        adapter.resolve_asset(source, "file/../outside.png")
    with pytest.raises(ValueError, match="Invalid"):
        adapter.resolve_asset(source, "zip/archive/member.png")


def test_originals_resolve_through_the_credential_profile_and_match_their_pinned_hash(tmp_path, monkeypatch, release):
    hub = FakeHub(monkeypatch, release.payloads())
    adapter = adapter_for(tmp_path, release)
    records, source = all_records(adapter)
    beyond = records[-1]  # a row long after the first hundred
    (asset,) = beyond.assets
    handle = adapter.resolve_asset(source, asset.uri)
    path = asset.uri[5:]
    assert handle.data == release.images[path] and handle.sha256 == hashlib.sha256(release.images[path]).hexdigest() == asset.sha256
    assert handle.media_type == "image/png"
    assert hub.calls and all(profile == "huggingface" for _, profile in hub.calls)  # the gated profile reaches every read
    assert adapter.media_bytes_fetched == hub.fetched == len(release.images[path])
    # a file without an LFS hash is verified against its Git blob SHA-1
    git_pinned = adapter.resolve_asset(source, "file/safety/s/p0.png")
    assert git_pinned.data == release.images["safety/s/p0.png"]


def test_a_changed_original_is_refused_not_served(tmp_path, monkeypatch, release):
    payloads = release.payloads()
    payloads[f"{BASE_URL}/safety/s/p0.png"] = release.images["safety/s/p1.png"]  # same length, other bytes: Git blob differs
    FakeHub(monkeypatch, payloads)
    adapter = adapter_for(tmp_path, release)
    _, source = all_records(adapter)
    with pytest.raises(ValueError, match="Git object"):
        adapter.resolve_asset(source, "file/safety/s/p0.png")


def test_the_transfer_limit_stops_reads_instead_of_exceeding_it(tmp_path, monkeypatch, release):
    FakeHub(monkeypatch, release.payloads())
    adapter = adapter_for(tmp_path, release)
    _, source = all_records(adapter)
    adapter.preparation_transfer_limit = len(release.images["safety/s/p1.png"]) + 10
    adapter.resolve_asset(source, "file/safety/s/p1.png")
    with pytest.raises(ValueError, match="transfer budget"):
        adapter.resolve_asset(source, "file/safety/s/p2.png")


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_read_says_why_and_what_to_do_and_never_leaks_the_token(tmp_path, monkeypatch, release, status):
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

    monkeypatch.setattr("dataset_atlas.storage.https._PinnedHTTPSConnection", Connection)
    monkeypatch.setattr("dataset_atlas.storage.https.HttpsFetcher._destination",
                        lambda self, url: (urlsplit(url).hostname, 443, "93.184.216.34", "/file"))
    monkeypatch.setenv("HF_TOKEN", FIXTURE_TOKEN)
    adapter = adapter_for(tmp_path, release)
    _, source = all_records(adapter)
    with pytest.raises(ValueError) as refused:
        adapter.resolve_asset(source, "file/safety/s/p1.png")
    message = str(refused.value)
    assert f"HTTP {status}" in message and "terms" in message and "sign in" in message and "Nothing was read" in message
    assert FIXTURE_TOKEN not in message and "Bearer" not in message


# --- refusals ------------------------------------------------------------------------------------------------------------


def test_a_task_file_that_is_not_pinned_is_refused(tmp_path, release):
    dataset = dataset_for(tmp_path, release)
    dataset.adapter_config["source_files"] = [f for f in dataset.adapter_config["source_files"] if f["source_name"] != "safety/s.csv"]
    with pytest.raises(ValueError, match="not among the pinned source files"):
        get_adapter(dataset).count


def test_a_native_field_that_collides_with_task_or_aspect_is_refused(tmp_path, release):
    release.queries["safety/s.csv"] = csv_bytes(["id", "task", "image_path"], [[0, "x", "p0.png"]])
    with pytest.raises(ValueError, match="reserved"):
        adapter_for(tmp_path, release).count


def test_an_unsafe_or_unknown_image_template_is_refused(tmp_path, release):
    release.tasks[1]["media"] = [img("safety/s/../{image_path}")]
    with pytest.raises(ValueError, match="unsafe"):
        adapter_for(tmp_path / "a", release).count
    release.tasks[1]["media"] = [img("safety/s/{image_path|rot13}")]
    with pytest.raises(ValueError, match="filter"):
        adapter_for(tmp_path / "b", release).count
    release.tasks[1]["media"] = [img("safety/s/{nonexistent}")]
    with pytest.raises(ValueError, match="does not hold"):
        adapter_for(tmp_path / "c", release).count


def test_a_changed_query_file_is_refused_by_its_checksum(tmp_path, release):
    adapter = adapter_for(tmp_path, release)
    target = Path(adapter.config["source_files"][0]["path"])
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum"):
        adapter.prepare(adapter.plan(5, 1_000_000))


# --- the whole preparation, end to end, on the synthetic suite ------------------------------------------------------------


def prepare_workspace(tmp_path, monkeypatch, name, budget=100_000_000, derive_snapshot=False):
    """An empty workspace holding only the catalogue entry and the real recipe, pointed at the synthetic suite."""
    from dataset_atlas.preparation import PreparationManager

    release = Release().build()
    root = tmp_path / name
    (root / "registry/datasets").mkdir(parents=True)
    (root / "registry/recipes").mkdir(parents=True)
    (root / "registry/media").mkdir(parents=True)
    media = json.dumps(release.inventory(), separators=(",", ":"), sort_keys=True)
    (root / "registry/media/multitrust.json").write_text(media)
    entry = yaml.safe_load(ENTRY_PATH.read_text())
    (root / "registry/datasets/multitrust.yaml").write_text(yaml.safe_dump(entry, sort_keys=False))
    document = recipe()
    document["expected_count"] = release.TOTAL_ROWS
    document["adapter_config"].pop("inventory_tasks", None)
    document["files"] = [{"source_name": n, "url": f"{BASE_URL}/{quote(n, safe='/')}", "bytes": len(d), "sha256": hashlib.sha256(d).hexdigest(),
                          "format": n.rsplit(".", 1)[1]} for n, d in release.queries.items()]
    document["preview_media_transfer_bytes"] = sum(len(d) for d in release.images.values())
    document["adapter_config"].update(tasks=release.tasks, media_inventory_sha256=hashlib.sha256(media.encode()).hexdigest(),
                                      fields={"task": {"dtype": "category", "values": [t["task"] for t in release.tasks], "description": "task"},
                                              "aspect": {"dtype": "category", "values": ASPECTS, "description": "aspect"}})
    if derive_snapshot:
        del document["snapshot_id"]
    (root / "registry/recipes/multitrust.yaml").write_text(yaml.safe_dump(document, sort_keys=False))
    hub = FakeHub(monkeypatch, release.payloads())
    monkeypatch.setenv("HF_TOKEN", FIXTURE_TOKEN)
    manager = PreparationManager(root)
    plan = manager.plan("multitrust", budget, 100_000_000)
    return root, manager, plan, release, hub


def test_planning_declares_the_upper_bound_and_the_credential_profile(tmp_path, monkeypatch):
    root, manager, plan, release, _ = prepare_workspace(tmp_path, monkeypatch, "plan")
    assert plan["ready"], plan["requirements"]
    assert plan["kind"] == "http_archive" and plan["credential_profile"] == "huggingface" and FIXTURE_TOKEN not in json.dumps(plan)
    queries = sum(len(d) for d in release.queries.values())
    assert plan["expected_download_bytes"] == queries + sum(len(d) for d in release.images.values()) and plan["download_is_upper_bound"]
    assert plan["preview_media_transfer_bytes"] == sum(len(d) for d in release.images.values())
    assert plan["expected_count"] == release.TOTAL_ROWS and plan["recipe_snapshot_id"] == recipe()["snapshot_id"]


def test_a_budget_below_the_declared_upper_bound_is_refused_at_planning(tmp_path, monkeypatch):
    root, manager, plan, release, hub = prepare_workspace(tmp_path, monkeypatch, "tight", budget=10_000)
    assert not plan["ready"] and any("exceeds the selected download budget" in r for r in plan["requirements"])
    assert hub.fetched == 0  # planning moves no bytes


def test_preparation_indexes_every_row_and_keeps_a_hundred_original_images(tmp_path, monkeypatch):
    import pyarrow.parquet as pq

    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry

    root, manager, plan, release, hub = prepare_workspace(tmp_path, monkeypatch, "first")
    assert plan["ready"], plan["requirements"]
    run(root, plan["id"])
    assert manager.status(plan["id"])["status"] == "completed"
    registry = Registry(root)
    dataset = registry.dataset("multitrust")
    assert dataset.snapshot_id == recipe()["snapshot_id"] and dataset.release == recipe()["release"]
    assert dataset.adapter == "multitrust" and dataset.adapter_config["credential_profile"] == "huggingface"
    coverage = dataset.coverage
    assert (coverage.preview_count, coverage.total_count) == (100, release.TOTAL_ROWS)
    assert (coverage.adapter, coverage.preview, coverage.complete_data) == ("tested", "complete_target", "indexed_metadata_partial_media")
    assert coverage.access == "gated" and coverage.identity == "resolved" and coverage.publication == "not_reviewed"
    pack = registry.pack("multitrust")
    assert len(pack.records) == 100 == len({r.id for r in pack.records})
    assert pack.sampling["method"] == "sha256_bottom_k_primary_asset_verified_media" and pack.sampling["seed"] == 0
    assert pack.sampling["population_count"] == release.TOTAL_ROWS and pack.sampling["returned_count"] == 100
    assert pack.sampling["grouping"] == "primary asset ID; record ID for records without assets" and pack.sampling["media_representation"] == "original"
    assert 100 <= pack.sampling["candidate_pool_count"] <= release.TOTAL_ROWS  # image clusters (rows sharing an image are one cluster)
    fields = {f.id: f for f in pack.fields}
    assert fields["source.task"].dtype == "category" and fields["source.aspect"].dtype == "category"
    assert fields["source.aspect"].values == ASPECTS
    version = registry.active_directory("multitrust")
    for record in pack.records:
        assert record.assets and all(a.uri for a in record.assets)  # a preview record always has its original image
        for asset in record.assets:
            kept = (version / "pack" / asset.uri).read_bytes()
            path = asset.metadata["source_ref"][5:]
            assert kept == release.images[path] and hashlib.sha256(kept).hexdigest() == asset.sha256 == pack.checksums[asset.uri]
    rows = pq.read_table(registry.snapshot_path("multitrust") / "records.parquet", columns=["record_json"]).column(0).to_pylist()
    complete = [json.loads(value) for value in rows]
    assert len(complete) == len({r["id"] for r in complete}) == release.TOTAL_ROWS
    assert sum(1 for r in complete if any(a["uri"] is None for a in r["assets"])) == release.ABSENT_REFERENCES  # absent images stay records
    assert sum(1 for r in complete if not r["assets"]) == release.ROWS_WITHOUT_IMAGE_BY_DESIGN
    receipt = json.loads((version / "receipt.json").read_text())
    assert receipt["snapshot_id"] == recipe()["snapshot_id"] and receipt["record_count"] == release.TOTAL_ROWS
    media = receipt["media_validation"]
    assert media["absent_media_references"] == release.ABSENT_REFERENCES and media["rows"] == release.TOTAL_ROWS
    # what moved is measured, stays within the declared upper bound, and the queries are not counted as images
    assert receipt["source_transfer_bytes"] == sum(len(d) for d in release.queries.values())
    assert 0 < receipt["remote_media_bytes"] <= plan["preview_media_transfer_bytes"]
    assert receipt["total_transfer_bytes"] == receipt["source_transfer_bytes"] + receipt["remote_media_bytes"] <= plan["expected_download_bytes"]
    assert hub.fetched == receipt["total_transfer_bytes"]
    assert all(profile == "huggingface" for _, profile in hub.calls) and len(hub.calls) > len(release.queries)  # queries and images alike
    # the credential is resolved at read time and never reaches a plan, a receipt, a pack or a prepared dataset file
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".yaml", ".jsonl", ".txt"}:
            assert FIXTURE_TOKEN not in path.read_text(errors="replace"), path.name


def test_an_empty_workspace_prepares_the_same_snapshot_and_the_same_preview(tmp_path, monkeypatch):
    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry

    seen = []
    for name in ("maintainer", "colleague"):
        root, manager, plan, release, _ = prepare_workspace(tmp_path, monkeypatch, name, derive_snapshot=True)
        run(root, plan["id"])
        registry = Registry(root)
        pack = registry.pack("multitrust")
        seen.append((registry.dataset("multitrust").snapshot_id, [r.id for r in pack.records]))
    assert seen[0] == seen[1] and seen[0][0].startswith("multitrust-")


def test_the_transfer_budget_never_changes_the_snapshot_or_which_records_the_preview_holds(tmp_path, monkeypatch):
    from dataset_atlas.preparation.worker import run
    from dataset_atlas.registry import Registry

    chosen = []
    for name, budget in (("tight", 1_000_000), ("generous", 50_000_000)):
        root, manager, plan, release, _ = prepare_workspace(tmp_path, monkeypatch, name, budget, derive_snapshot=True)
        assert plan["ready"], plan["requirements"]
        run(root, plan["id"])
        registry = Registry(root)
        chosen.append((registry.dataset("multitrust").snapshot_id, [r.id for r in registry.pack("multitrust").records]))
    assert chosen[0] == chosen[1]


# --- the registry entry, the receipts and the recipe agree ---------------------------------------------------------------


def entry() -> dict:
    return yaml.safe_load(ENTRY_PATH.read_text())


def test_entry_coverage_states_each_dimension_separately_and_keeps_the_limits():
    coverage = entry()["coverage"]
    assert coverage["identity"] == "resolved" and coverage["source"] == "verified"
    resolution = next(item for item in entry()["evidence"] if item["kind"] == "source_release_resolution")
    assert resolution["status"] == "resolved_declared_source_population"
    assert resolution["release"] == recipe()["release"]
    assert "not human review" in resolution["scope_note"]
    assert "historical paper-membership acceptance" in resolution["scope_note"]
    assert coverage["access"] == "gated"  # the terms are the researcher's own; the entry stays gated
    assert coverage["adapter"] == "tested" and coverage["preview"] == "complete_target"
    assert coverage["preview_count"] == 100 and coverage["unit"] == "example"
    assert coverage["complete_data"] == "indexed_metadata_partial_media"
    assert coverage["total_count"] == recipe()["expected_count"] == 12_616
    assert resolution["record_count"] == 11_512
    completion = next(item for item in entry()["evidence"] if item["kind"] == "native_unit_completion")
    assert completion["record_count"] == coverage["total_count"]
    assert coverage["publication"] == "not_reviewed"
    blockers = " ".join(coverage["blockers"])
    assert "heterogeneous" in blockers and "not one homogeneous collection" in blockers
    assert "Component source datasets" in blockers
    historical = " ".join(str(item) for item in entry()["evidence"] if item["kind"] == "paper_usage_qualification")
    assert "transfer attacks" in historical and "not located" in historical
    assert "accept" in blockers and "redistribution" in blockers
    source_history = " ".join(str(item) for item in entry()["evidence"])
    assert "2026-10-09" in source_history and "auth_check" in source_history
    assert "per-task adapters" not in blockers and "implementation gap" not in blockers  # the old claim is gone
    assert "no inventory, adapter or preview exists" not in blockers
    assert entry()["adapter"] == "multitrust" and entry()["adapter_config"] == {} and entry()["release"] == recipe()["release"]
    assert entry()["rights"]["images"] == entry()["rights"]["records"] == "not_reviewed"


def test_description_lists_every_member_task_by_aspect():
    description = entry()["description"]
    for item in recipe()["adapter_config"]["tasks"]:
        assert item["task"] in description, item["task"]
    for aspect, rows in {"truthfulness": 2540, "safety": 798, "robustness": 4199, "fairness": 1209, "privacy": 2766}.items():
        assert f"{aspect.capitalize()} ({rows:,}" in description
    assert "one record per query row" in description.lower()
    assert "1,104" in description and "12,616" in description


def test_source_resolution_and_native_units_do_not_approve_historical_use_or_publication():
    now = entry()
    source = next(item for item in now["evidence"] if item["kind"] == "source_release_resolution")
    completion = next(item for item in now["evidence"] if item["kind"] == "native_unit_completion")
    assert source["status"] == "resolved_declared_source_population"
    assert "not human review" in source["scope_note"]
    assert "historical-paper acceptance" in completion["scope_note"]
    assert "no" in completion["scope_note"].lower()
    assert source["record_count"] == 11_512 and completion["record_count"] == 12_616
    assert now["rights"]["records"] == now["rights"]["images"] == "not_reviewed"
    assert now["coverage"]["publication"] == "not_reviewed"
    assert not TOKEN_PATTERN.search(ENTRY_PATH.read_text())
