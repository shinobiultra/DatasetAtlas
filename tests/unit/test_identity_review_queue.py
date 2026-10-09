"""scripts/build_identity_review_queue.py turns unresolved catalogue identities into decisions for a person.

The queue is read-only over the registry: it never edits an entry, never changes `coverage.identity`, `release`, `preview`
or any other field, and never presents a family link as coverage. Only a person changes an identity.

Decisions go to their own builder-owned file, `work/corpus/identity_review_queue.jsonl`; the corpus pipeline's
`work/corpus/review_queue.jsonl` (a per-paper queue) is never touched.

Tests on the real registry derive what they expect from the registry and the coverage CSV themselves, so routine later work
(a refreshed source, a new adapter, a resolved identity) never turns them red. Tests that write use a copy in `tmp_path`.
"""
import csv
import hashlib
import importlib.util
import json
import re
import shutil
import socket
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build_identity_review_queue.py"
spec = importlib.util.spec_from_file_location("build_identity_review_queue", SCRIPT)
assert spec is not None and spec.loader is not None
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

IN_SCOPE = {"candidate", "family_or_variant_candidate"}
IDS_FILE = "registry/identity-review-ids.json"
QUEUE_FILE = "work/corpus/identity_review_queue.jsonl"
CORPUS_QUEUE = "work/corpus/review_queue.jsonl"
STALE_BLOCKER = re.compile(r"not implemented|no (?:local )?preview", re.I)
ABSOLUTE_PATH = re.compile(r"(?<![\w.:/-])/(?:home|tmp|usr|var|mnt|opt|etc|Users|root)/|\b[A-Za-z]:\\")
CONFIDENCE_WORDS = ("confident", "confidence", "likely", "probably", "recommend")


# --- helpers -----------------------------------------------------------------------------------------------------------

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_tree(directory: Path) -> dict:
    return {str(p.relative_to(directory)): _sha(p) for p in sorted(directory.rglob("*")) if p.is_file()}


def _real_registry() -> dict:
    """The registry as plain YAML, read without the builder."""
    return {d["id"]: d for d in (yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "registry/datasets").glob("*.yaml")))}


def _dataset_row(dataset_id: str) -> dict:
    with (ROOT / "reports/dataset_coverage.csv").open(newline="", encoding="utf-8") as stream:
        return {row["dataset_id"]: row for row in csv.DictReader(stream)}[dataset_id]


def _workspace(tmp_path: Path, *, with_ids: bool = True) -> Path:
    """A throwaway copy of the inputs: registry entries, coverage CSV, the committed id mapping and the corpus review queue."""
    shutil.copytree(ROOT / "registry/datasets", tmp_path / "registry/datasets")
    (tmp_path / "reports").mkdir()
    shutil.copy(ROOT / "reports/dataset_coverage.csv", tmp_path / "reports/dataset_coverage.csv")
    if with_ids and (ROOT / IDS_FILE).exists():
        shutil.copy(ROOT / IDS_FILE, tmp_path / IDS_FILE)
    (tmp_path / "work/corpus").mkdir(parents=True)
    if (ROOT / CORPUS_QUEUE).exists():
        shutil.copy(ROOT / CORPUS_QUEUE, tmp_path / CORPUS_QUEUE)
    else:
        lines = [json.dumps({"kind": "extraction_quality", "paper_id": f"paper-{n}", "status": "reviewed"}) for n in range(3)]
        (tmp_path / CORPUS_QUEUE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


def _entry(entry_id, *, name=None, identity="candidate", access="public", adapter="not_started", preview="none", links=(),
           papers=(), blockers=(), evidence=(), description=""):
    mentions = [{"kind": "corpus_mention", "evidence_id": f"evidence-{entry_id}-{n}", "paper_id": paper_id, "page": 3,
                 "role": "evaluation", "excerpt": excerpt} for n, (paper_id, excerpt) in enumerate(papers)]
    return {"schema_version": "1.0", "id": entry_id, "name": name or entry_id, "aliases": [], "description": description,
            "paper_ids": sorted({paper_id for paper_id, _ in papers}), "release": "unresolved",
            "coverage": {"identity": identity, "source": "unverified", "access": access, "adapter": adapter, "preview": preview,
                         "blockers": list(blockers)},
            "evidence": mentions + list(evidence), "relationships": list(links) or None}


def _link(kind, target, spelling="target_id"):
    return {"type": kind, spelling: target, "status": "asserted_from_source_review"}


def _synthetic(tmp_path: Path, *entries, csv_rows=()) -> Path:
    directory = tmp_path / "registry/datasets"
    directory.mkdir(parents=True)
    for entry in entries:
        (directory / f"{entry['id']}.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")
    if csv_rows:
        (tmp_path / "reports").mkdir()
        with (tmp_path / "reports/dataset_coverage.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(csv_rows)
    return tmp_path


def _member(model, entry_id):
    return next(m for g in model.groups for m in g.members if m.id == entry_id)


def _group_of(model, entry_id):
    return next(g for g in model.groups if any(m.id == entry_id for m in g.members))


def _groups_by_members(model):
    return {frozenset(m.id for m in g.members) for g in model.groups}


def _ids(model) -> dict:
    return {g.key: g.id for g in model.groups}


def _section(markdown: str, heading: str) -> str:
    """The body of one `## ` section."""
    match = re.search(rf"^## {re.escape(heading)}.*?(?=^## |\Z)", markdown, re.M | re.S)
    assert match, heading
    return match.group(0)


def _read_records(path: Path) -> list:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _record(root: Path, record_id: str) -> dict:
    found = [r for r in _read_records(root / QUEUE_FILE) if r.get("id") == record_id]
    assert len(found) == 1, record_id
    return found[0]


def _set_identity(root: Path, entry_id: str, identity: str) -> None:
    path = root / "registry/datasets" / f"{entry_id}.yaml"
    entry = yaml.safe_load(path.read_text(encoding="utf-8"))
    entry["coverage"]["identity"] = identity
    path.write_text(yaml.safe_dump(entry), encoding="utf-8")


def _add_entry(root: Path, entry: dict) -> None:
    (root / "registry/datasets" / f"{entry['id']}.yaml").write_text(yaml.safe_dump(entry), encoding="utf-8")


def _rewrite_record(root: Path, record_id: str, **changes) -> None:
    lines = (root / QUEUE_FILE).read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines):
        item = json.loads(line)
        if item.get("id") == record_id:
            lines[number] = json.dumps({**item, **changes}, ensure_ascii=False)
    (root / QUEUE_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def real_model():
    return builder.build_model(ROOT)


@pytest.fixture(scope="module")
def real_markdown(real_model):
    return builder.render_markdown(real_model)


# --- coverage: every unresolved identity exactly once -------------------------------------------------------------------

def test_queue_covers_every_candidate_and_family_entry_exactly_once(real_model):
    expected = sorted(entry_id for entry_id, d in _real_registry().items() if d["coverage"]["identity"] in IN_SCOPE)
    listed = [m.id for g in real_model.groups for m in g.members]
    assert expected, "the real registry has candidate entries"
    assert sorted(listed) == expected
    assert len(listed) == len(set(listed))
    assert all(len(g.members) >= 1 for g in real_model.groups)


def test_resolved_entries_are_never_members(real_model):
    resolved = {entry_id for entry_id, d in _real_registry().items() if d["coverage"]["identity"] not in IN_SCOPE}
    assert resolved and not resolved & {m.id for g in real_model.groups for m in g.members}


def test_groups_connect_only_entries_the_registry_links_to_a_shared_target(tmp_path):
    root = _synthetic(
        tmp_path,
        _entry("target-a", identity="resolved"), _entry("target-b", identity="resolved"),
        _entry("alias-1", name="Alias One", links=[_link("same_source_family_as", "target-a")]),
        _entry("alias-2", name="Alias Two", links=[_link("derived_from", "target-a", spelling="target")]),
        _entry("alias-3", name="Alias Three", links=[_link("annotation_overlay_of", "target-b")]),
        _entry("alias-both", links=[_link("source_subset_of", "target-a"), _link("same_source_family_as", "target-b")]),
        _entry("alias-1b", name="Alias One"),                     # a near-identical name is not a link
        _entry("loner"),
        _entry("pointer", links=[_link("possible_source_for", "target-a")]),   # not one of the four grouping link types
        _entry("settled-link", identity="resolved", links=[_link("same_source_family_as", "target-a")]))
    model = builder.build_model(root)
    assert _groups_by_members(model) == {frozenset({"alias-1", "alias-2", "alias-3", "alias-both"}), frozenset({"alias-1b"}),
                                         frozenset({"loner"}), frozenset({"pointer"})}
    family = _group_of(model, "alias-1")
    assert family.key == "target-a|target-b"           # the sorted link targets
    assert _group_of(model, "loner").key == "loner"    # an unlinked entry is its own group, keyed by its id
    assert [t.id for t in family.targets] == ["target-a", "target-b"]


def test_an_unlinked_in_queue_target_joins_the_entries_that_link_to_it(tmp_path):
    root = _synthetic(tmp_path, _entry("middle"), _entry("leaf", links=[_link("derived_from", "middle")]))
    model = builder.build_model(root)
    assert _groups_by_members(model) == {frozenset({"middle", "leaf"})}
    assert _group_of(model, "leaf").key == "middle"                 # both carry the node `middle`
    assert [t.id for t in _group_of(model, "leaf").targets] == ["middle"]


def test_a_linked_in_queue_target_keeps_the_group_its_own_targets_give_it(tmp_path):
    """The grouping rule is exactly 'same link target'; an entry linked to an in-queue entry that links elsewhere is keyed by that id."""
    root = _synthetic(tmp_path, _entry("base", identity="resolved"), _entry("middle", links=[_link("same_source_family_as", "base")]),
                      _entry("leaf", links=[_link("derived_from", "middle")]))
    model = builder.build_model(root)
    assert _groups_by_members(model) == {frozenset({"middle"}), frozenset({"leaf"})}
    assert (_group_of(model, "middle").key, _group_of(model, "leaf").key) == ("base", "middle")


# --- stable IDs --------------------------------------------------------------------------------------------------------

def test_ids_are_stable_across_runs(tmp_path):
    first_root = _workspace(tmp_path / "first", with_ids=False)
    first = builder.run(first_root)
    mapping_path = first_root / IDS_FILE
    mapping_text = mapping_path.read_text(encoding="utf-8")
    mapping = json.loads(mapping_text)
    assert mapping == _ids(first) and mapping_text.endswith("\n")
    assert list(mapping) == sorted(mapping), "keys are written sorted"
    assert list(mapping.values()) == [f"IR-{n:03d}" for n in range(1, len(mapping) + 1)], "a fresh mapping numbers the sorted keys 001, 002, ..."
    mtime = mapping_path.stat().st_mtime_ns

    second = builder.run(first_root)                      # the mapping now exists: nothing new, nothing rewritten
    assert _ids(second) == _ids(first)
    assert mapping_path.read_text(encoding="utf-8") == mapping_text and mapping_path.stat().st_mtime_ns == mtime

    third = builder.run(_workspace(tmp_path / "third", with_ids=False))   # same input, no mapping: same IDs
    assert _ids(third) == _ids(first)


def test_the_committed_mapping_is_not_renumbered_by_a_run(tmp_path, real_model):
    committed = ROOT / IDS_FILE
    if not committed.exists():
        pytest.skip("the id mapping has not been generated yet")
    root = _workspace(tmp_path)
    builder.run(root)
    after = json.loads((root / IDS_FILE).read_text(encoding="utf-8"))
    before = json.loads(committed.read_text(encoding="utf-8"))
    assert set(before.values()) <= set(after.values()), "an id is never dropped, whether its group is live or retired"
    assert {g.key: g.id for g in real_model.groups} == {key: after[key] for key in {g.key for g in real_model.groups}}


def test_the_committed_mapping_is_well_formed():
    text = (ROOT / IDS_FILE).read_text(encoding="utf-8")
    mapping = json.loads(text)
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert list(mapping) == sorted(mapping)
    assert all(re.fullmatch(r"IR-\d{3,}", value) for value in mapping.values())
    assert len(set(mapping.values())) == len(mapping), "an IR id is never shared by two groups"


def test_adding_a_new_in_scope_entry_does_not_renumber_existing_groups(tmp_path):
    root = _workspace(tmp_path, with_ids=False)
    first = builder.run(root)
    before = _ids(first)
    registry = root / "registry/datasets"
    assert any(len(group.members) > 1 for group in first.groups), "the registry has linked families"
    coco_key = next(key for key in before if "coco" in key.split("|"))
    for new in (
        _entry("aaa-sorts-before-everything", name="Sorts first"),
        _entry("zzz-sorts-after-everything", name="Sorts last"),
        _entry("new-coco-alias", name="New COCO alias", links=[_link("same_source_family_as", "coco")]),
    ):
        (registry / f"{new['id']}.yaml").write_text(yaml.safe_dump(new), encoding="utf-8")
    # A person resolves one existing entry: its group may vanish, but nobody else is renumbered.
    resolved_id = next(g.key for g in first.groups if len(g.members) == 1 and g.key == g.members[0].id)
    resolved_path = registry / f"{resolved_id}.yaml"
    assert resolved_path.exists()
    resolved = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    resolved["coverage"]["identity"] = "resolved"
    resolved_path.write_text(yaml.safe_dump(resolved), encoding="utf-8")

    after_model = builder.run(root)
    after = _ids(after_model)
    assert {key: after[key] for key in before if key != resolved_id} == {key: before[key] for key in before if key != resolved_id}
    assert after[coco_key] == before[coco_key]
    assert "new-coco-alias" in {m.id for m in _group_of(after_model, "new-coco-alias").members}
    assert _group_of(after_model, "new-coco-alias").id == before[coco_key]
    brand_new = {key: after[key] for key in after if key not in before}
    assert set(brand_new) == {"aaa-sorts-before-everything", "zzz-sorts-after-everything"}
    top = max(int(value.removeprefix("IR-")) for value in before.values())
    assert sorted(brand_new.values()) == [f"IR-{top + 1:03d}", f"IR-{top + 2:03d}"], "new keys take the next free numbers, in sorted-key order"
    assert brand_new["aaa-sorts-before-everything"] == f"IR-{top + 1:03d}"
    assert json.loads((root / IDS_FILE).read_text(encoding="utf-8"))[resolved_id] == before[resolved_id], "an assignment is never dropped"


# --- the registry is never touched -------------------------------------------------------------------------------------

def test_running_the_builder_leaves_registry_bytes_unchanged(tmp_path):
    real_before = _hash_tree(ROOT / "registry/datasets")
    csv_before = _sha(ROOT / "reports/dataset_coverage.csv")
    builder.render_markdown(builder.build_model(ROOT))     # the whole computation, on the real tree
    assert _hash_tree(ROOT / "registry/datasets") == real_before
    assert _sha(ROOT / "reports/dataset_coverage.csv") == csv_before

    root = _workspace(tmp_path, with_ids=False)
    registry_before = _hash_tree(root / "registry")
    csv_copy = _sha(root / "reports/dataset_coverage.csv")
    builder.run(root)
    registry_after = _hash_tree(root / "registry")
    created = set(registry_after) - set(registry_before)
    assert created == {"identity-review-ids.json"}
    assert {name: digest for name, digest in registry_after.items() if name not in created} == registry_before
    assert _sha(root / "reports/dataset_coverage.csv") == csv_copy


def test_builder_needs_no_network(monkeypatch, tmp_path):
    def refuse(*args, **kwargs):
        raise AssertionError("the identity review queue must not use the network")
    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    builder.run(_workspace(tmp_path, with_ids=False))


def test_the_ids_file_is_not_a_catalogue_entry():
    from dataset_atlas.registry import Registry
    ids = Registry(ROOT).ids()
    assert len(ids) == len(list((ROOT / "registry/datasets").glob("*.yaml")))
    assert not any("identity-review" in entry_id for entry_id in ids)
    assert not (ROOT / "registry/datasets" / "identity-review-ids.json").exists()


# --- a family link is navigation, not coverage (Review Focus 6) -----------------------------------------------------------

def test_family_link_does_not_change_preview_state(real_model, real_markdown):
    assert _dataset_row("nips17")["preview"] == "none"
    assert _real_registry()["nips17"]["coverage"]["preview"] == "none"
    member = _member(real_model, "nips17")
    assert member.preview == "none"
    group = _group_of(real_model, "nips17")
    coco = next(target for target in group.targets if target.id == "saegis-clean-and-adversarial-splits")
    assert coco.preview == _dataset_row("saegis-clean-and-adversarial-splits")["preview"], "the family's own state is shown as it is"
    assert any(link.target == "saegis-clean-and-adversarial-splits" for link in member.links)
    found = re.search(r"^### `nips17`.*?(?=^### |^## |\Z)", real_markdown, re.M | re.S)
    assert found and "preview `none`" in found.group(0)


def test_a_member_never_inherits_the_preview_of_a_link_target(real_model):
    with (ROOT / "reports/dataset_coverage.csv").open(newline="", encoding="utf-8") as stream:
        rows = {row["dataset_id"]: row for row in csv.DictReader(stream)}
    for group in real_model.groups:
        for member in group.members:
            assert member.preview == rows[member.id]["preview"], member.id
            assert member.adapter == rows[member.id]["adapter"], member.id


def test_an_alias_without_a_preview_stays_none_beside_a_prepared_family(tmp_path):
    rows = [{"dataset_id": "family", "identity": "resolved", "access": "public", "adapter": "tested", "preview": "complete_target"},
            {"dataset_id": "alias", "identity": "candidate", "access": "public", "adapter": "not_started", "preview": "none"}]
    root = _synthetic(tmp_path, _entry("family", identity="resolved", adapter="tested", preview="complete_target"),
                      _entry("alias", links=[_link("same_source_family_as", "family")]), csv_rows=rows)
    model = builder.build_model(root)
    assert _member(model, "alias").preview == "none"
    assert _group_of(model, "alias").targets[0].preview == "complete_target"
    markdown = builder.render_markdown(model)
    assert "prepared" in markdown and "preview `none`" in markdown


def test_state_comes_from_the_coverage_csv_and_falls_back_to_the_registry(tmp_path):
    rows = [{"dataset_id": "in-csv", "identity": "candidate", "access": "public", "adapter": "tested", "preview": "complete_target"}]
    root = _synthetic(tmp_path, _entry("in-csv", adapter="not_started", preview="none"),
                      _entry("not-in-csv", adapter="not_started", preview="local_only"), csv_rows=rows)
    model = builder.build_model(root)
    assert (_member(model, "in-csv").preview, _member(model, "in-csv").adapter) == ("complete_target", "tested")
    assert (_member(model, "not-in-csv").preview, _member(model, "not-in-csv").adapter) == ("local_only", "not_started")


# --- blocker types and the decision ------------------------------------------------------------------------------------

def test_blocker_type_is_read_from_the_registry_not_guessed(tmp_path):
    outage = {"kind": "source_audit_access", "checked_on": "2026-10-08", "url": "http://host.example/a.avi", "note": "no DNS",
              "source_identity_status": "author_page_identified_media_host_unresolvable", "audit_file": "reports/gate-check-20261008.json"}
    older_outage = dict(outage, checked_on="2026-10-06", source_identity_status="author_page_identified_media_host_unresponsive")
    recovered = {"kind": "source_audit_access", "checked_on": "2026-10-09", "url": "http://host.example/a.avi", "note": "ok",
                 "source_identity_status": "official_files_reachable"}
    root = _synthetic(
        tmp_path,
        _entry("family", identity="resolved", adapter="tested", preview="complete_target"),
        _entry("paper-private", access="unreleased", adapter="not_applicable"),
        _entry("gated-one", access="gated", links=[_link("same_source_family_as", "family")]),
        _entry("asked", access="request_required"),
        _entry("author-asked", access="author_request_required"),
        _entry("alias", links=[_link("same_source_family_as", "family")]),
        _entry("plain", access="source_release_unverified"),
        _entry("host-down", evidence=[outage]),
        _entry("host-down-and-gated", access="gated", evidence=[outage]),
        _entry("host-back", evidence=[older_outage, recovered]))
    model = builder.build_model(root)
    types = {m.id: m.blocker_type for g in model.groups for m in g.members}
    assert types == {"paper-private": "unreleased", "gated-one": "access", "asked": "access", "author-asked": "access",
                     "alias": "identity", "plain": "identity", "host-down": "source_availability",
                     "host-down-and-gated": "access", "host-back": "identity"}
    assert "unresolvable" in _member(model, "host-down").blocker_basis and "2026-10-08" in _member(model, "host-down").blocker_basis
    assert "same_source_family_as" in _member(model, "alias").blocker_basis
    assert model.blocker_counts == {"identity": 3, "access": 4, "unreleased": 1, "source_availability": 1, "adapter": 0}


def test_options_and_decision_are_stated_from_the_groups_structure(tmp_path):
    root = _synthetic(
        tmp_path,
        _entry("family-a", identity="resolved", adapter="tested", preview="complete_target"),
        _entry("family-b", identity="resolved", adapter="tested", preview="complete_target"),
        _entry("alias-1", links=[_link("same_source_family_as", "family-a")]),
        _entry("alias-2", links=[_link("same_source_family_as", "family-a"), _link("derived_from", "family-b")]),
        _entry("paper-private", access="unreleased", adapter="not_applicable"),
        _entry("gated-one", access="gated"),
        _entry("alone"))
    model = builder.build_model(root)
    family = _group_of(model, "alias-1")
    assert family.options == ["alias_of:family-a", "alias_of:family-b", "distinct_release", "keep_candidate"]
    assert _member(model, "alias-1").options == ["alias_of:family-a", "distinct_release", "keep_candidate"]
    assert _member(model, "alias-2").options == ["alias_of:family-a", "alias_of:family-b", "distinct_release", "keep_candidate"]
    assert "alias_of:family-a" in " ".join(family.decision) and "prepared" in " ".join(family.decision)

    private = _group_of(model, "paper-private")
    assert private.options == ["accept_unreleased_custom_record", "keep_candidate"]
    assert "unreleased paper-private record: accept as an unreleased custom record, or keep as candidate" in " ".join(private.decision)

    gated = _group_of(model, "gated-one")
    assert "the blocker is access" in " ".join(gated.decision) and "not identity" in " ".join(gated.decision)
    assert gated.options == ["distinct_release", "keep_candidate"]

    assert _group_of(model, "alone").options == ["distinct_release", "keep_candidate"]
    assert "no registry link" in " ".join(_group_of(model, "alone").decision)


def test_public_entries_without_an_adapter_state_what_blocks_them(real_model, real_markdown):
    rows = [m for g in real_model.groups for m in g.members if m.access == "public" and m.adapter == "not_started"]
    assert rows, "the registry has public entries whose adapter is not started"
    for member in rows:
        assert member.blocker_type in {"identity", "source_availability"}, member.id
        linked = {link.target for link in member.links}
        if any(t.preview != "none" for t in _group_of(real_model, member.id).targets if t.id in linked):
            assert member.blocker_type == "identity", member.id      # a family alias of an already prepared release
    section = _section(real_markdown, "Public sources whose adapter is not started")
    for member in rows:
        assert f"`{member.id}`" in section
        assert re.search(rf"`{re.escape(member.id)}`[^\n]*\*\*(identity|source_availability)\*\*", section), member.id
    assert len(re.findall(r"^- `", section, re.M)) == len(rows)


def test_no_member_has_the_adapter_blocker_because_the_queue_holds_only_unsettled_identities(real_model):
    assert real_model.blocker_counts["adapter"] == 0
    assert all(m.blocker_type != "adapter" for g in real_model.groups for m in g.members)
    assert sum(real_model.blocker_counts.values()) == sum(len(g.members) for g in real_model.groups)


# --- blockers come from the merged view (no contradiction with the state beside them) --------------------------------------

def test_no_member_quotes_a_blocker_that_its_own_state_contradicts(real_model):
    for group in real_model.groups:
        for member in group.members:
            if member.adapter in {"tested", "implemented"} or member.preview in {"complete_target", "local_only"}:
                stale = [line for line in member.registry_blockers if STALE_BLOCKER.search(line)]
                assert not stale, (member.id, member.adapter, member.preview, stale)


def test_only_the_phrases_the_registry_itself_removes_are_dropped_from_the_blockers(real_model):
    registry = _real_registry()
    for group in real_model.groups:
        for member in group.members:
            lines = [" ".join(str(line).split()) for line in registry[member.id]["coverage"]["blockers"]]
            assert member.registry_blockers == [line for line in lines if line in member.registry_blockers], member.id   # order kept
            assert set(lines) - set(member.registry_blockers) <= builder.OBSOLETE_BLOCKERS, member.id


def test_the_obsolete_blocker_phrases_are_the_ones_the_registry_removes():
    import inspect
    from dataset_atlas.preparation import prepared_metadata
    source = inspect.getsource(prepared_metadata)
    assert builder.OBSOLETE_BLOCKERS
    for phrase in builder.OBSOLETE_BLOCKERS:
        assert f"'{phrase}'" in source, phrase


def test_blockers_follow_the_merged_view_but_keep_lines_the_older_csv_does_not_know(tmp_path):
    gone = "Adapter and preview are not implemented."
    rights = "Original release identity and rights need verification."
    newer = "Checked 2026-10-09: a line written after the coverage CSV was generated."
    rows = [{"dataset_id": "prepared", "identity": "candidate", "access": "public", "adapter": "tested", "preview": "complete_target",
             "blockers": rights},                                                       # the merged view dropped `gone`
            {"dataset_id": "unprepared", "identity": "candidate", "access": "public", "adapter": "not_started", "preview": "none",
             "blockers": f"{rights} | {gone}"}]                                          # the merged view kept it
    root = _synthetic(tmp_path,
                      _entry("prepared", blockers=[rights, gone, newer]),
                      _entry("unprepared", blockers=[rights, gone]),
                      _entry("no-row", blockers=[gone, newer]),                          # no CSV row: the registry's own list
                      csv_rows=rows)
    model = builder.build_model(root)
    assert _member(model, "prepared").registry_blockers == [rights, newer]
    assert _member(model, "unprepared").registry_blockers == [rights, gone]
    assert _member(model, "no-row").registry_blockers == [gone, newer]


def test_a_csv_without_a_blockers_column_leaves_the_registry_list_alone(tmp_path):
    rows = [{"dataset_id": "a", "identity": "candidate", "access": "public", "adapter": "tested", "preview": "complete_target"}]
    root = _synthetic(tmp_path, _entry("a", blockers=["Adapter and preview are not implemented.", "Other."]), csv_rows=rows)
    assert _member(builder.build_model(root), "a").registry_blockers == ["Adapter and preview are not implemented.", "Other."]


# --- the people and papers behind each name ------------------------------------------------------------------------------

def test_each_paper_appears_once_per_member_with_a_short_excerpt(tmp_path, real_model):
    for group in real_model.groups:
        for member in group.members:
            paper_ids = [p.paper_id for p in member.papers]
            assert len(paper_ids) == len(set(paper_ids)), member.id
            assert all(len(p.excerpt) <= 200 for p in member.papers), member.id
    long_excerpt = "word " * 80
    root = _synthetic(tmp_path, _entry("many", papers=[("paper-1", "first"), ("paper-1", "second, same paper"), ("paper-2", long_excerpt)]))
    papers = _member(builder.build_model(root), "many").papers
    assert [(p.paper_id, p.page, p.role) for p in papers] == [("paper-1", 3, "evaluation"), ("paper-2", 3, "evaluation")]
    assert papers[0].excerpt == "first" and len(papers[1].excerpt) <= 200 and papers[1].excerpt.endswith("…")


# --- the decision file (builder-owned) --------------------------------------------------------------------------------

def test_decisions_go_to_their_own_file_and_the_corpus_review_queue_is_untouched(tmp_path):
    root = _workspace(tmp_path, with_ids=False)
    corpus = root / CORPUS_QUEUE
    corpus_before = corpus.read_bytes()
    first = builder.run(root)
    assert corpus.read_bytes() == corpus_before, "the corpus pipeline's per-paper queue is never touched"
    assert all(json.loads(line).get("kind") != "identity_decision" for line in corpus.read_text(encoding="utf-8").splitlines() if line.strip())
    records = _read_records(root / QUEUE_FILE)
    assert len(records) == len(first.groups)
    for record, group in zip(records, first.groups):
        assert list(record) == ["kind", "id", "group_key", "members", "status", "options", "created_by"]
        assert record == {"kind": "identity_decision", "id": group.id, "group_key": group.key,
                          "members": sorted(m.id for m in group.members), "status": "open", "options": group.options,
                          "created_by": "build_identity_review_queue.py"}
    assert len({r["id"] for r in records}) == len(records)
    written = (root / QUEUE_FILE).read_bytes()
    builder.run(root)
    assert (root / QUEUE_FILE).read_bytes() == written, "a second run changes nothing"
    assert corpus.read_bytes() == corpus_before


def test_the_real_corpus_review_queue_holds_no_identity_decision():
    real = ROOT / CORPUS_QUEUE
    if not real.exists():
        pytest.skip("work/corpus/review_queue.jsonl is not present (git-ignored)")
    kinds = {json.loads(line).get("kind") for line in real.read_text(encoding="utf-8").splitlines() if line.strip()}
    assert "identity_decision" not in kinds


def test_a_foreign_line_and_a_missing_trailing_newline_in_the_decision_file_are_kept(tmp_path):
    root = _workspace(tmp_path, with_ids=False)
    foreign = json.dumps({"kind": "note", "text": "kept as written"})
    (root / QUEUE_FILE).write_text(foreign, encoding="utf-8")                 # no trailing newline
    model = builder.run(root)
    text = (root / QUEUE_FILE).read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == foreign and len(lines) == 1 + len(model.groups) and text.endswith("\n")
    assert all(json.loads(line) for line in lines)


def test_a_decision_file_that_is_not_json_stops_the_run_before_anything_is_written(tmp_path):
    root = _workspace(tmp_path, with_ids=False)
    (root / QUEUE_FILE).write_text("not json\n", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        builder.run(root)
    assert not (root / IDS_FILE).exists() and not (root / "reports/identity_review_queue.md").exists()
    assert (root / QUEUE_FILE).read_text(encoding="utf-8") == "not json\n"


def test_a_missing_decision_file_is_created(tmp_path):
    root = _workspace(tmp_path, with_ids=False)
    assert not (root / QUEUE_FILE).exists()
    model = builder.run(root)
    assert len(_read_records(root / QUEUE_FILE)) == len(model.groups)


def test_an_open_record_is_refreshed_not_duplicated_when_its_group_changes(tmp_path):
    root = _synthetic(tmp_path, _entry("target", identity="resolved"), _entry("alias-1", links=[_link("same_source_family_as", "target")]))
    builder.run(root)
    assert _record(root, "IR-001")["members"] == ["alias-1"]
    _add_entry(root, _entry("alias-2", links=[_link("same_source_family_as", "target")]))
    _add_entry(root, _entry("other"))
    builder.run(root)
    records = _read_records(root / QUEUE_FILE)
    assert [r["id"] for r in records] == ["IR-001", "IR-002"], "the grown group keeps IR-001; nothing is appended twice"
    assert records[0]["members"] == ["alias-1", "alias-2"], "while a record is open its members are a snapshot refreshed on every run"
    assert list(records[0]) == ["kind", "id", "group_key", "members", "status", "options", "created_by"]


def test_a_record_with_any_other_status_is_never_altered(tmp_path):
    root = _synthetic(tmp_path, _entry("target", identity="resolved"), _entry("alias-1", links=[_link("same_source_family_as", "target")]),
                      _entry("loner"))
    first = builder.run(root)
    grown, lost = _group_of(first, "alias-1").id, _group_of(first, "loner").id
    _rewrite_record(root, grown, status="decided", decision="alias_of:target")
    _rewrite_record(root, lost, status="deferred")
    lines_before = (root / QUEUE_FILE).read_text(encoding="utf-8").splitlines()
    _add_entry(root, _entry("alias-2", links=[_link("same_source_family_as", "target")]))      # the decided group grows
    _set_identity(root, "loner", "resolved")                                                   # the deferred group disappears
    second = builder.run(root)
    assert (grown, "target") not in second.retired and lost in {i for i, _ in second.retired}
    assert (root / QUEUE_FILE).read_text(encoding="utf-8").splitlines() == lines_before, "a person's recorded status is never overwritten"


# --- ids survive a person's decisions ---------------------------------------------------------------------------------

@pytest.mark.parametrize("resolved, member", [("a2", "a1")])
def test_resolving_one_member_keeps_the_groups_id(tmp_path, resolved, member):
    # Two prepared families; a2 bridges both, so the group key names both and changes once a2 is resolved.
    root = _synthetic(tmp_path, _entry("t1", identity="resolved"), _entry("t2", identity="resolved"),
                      _entry("a1", links=[_link("same_source_family_as", "t1")]),
                      _entry("a2", links=[_link("same_source_family_as", "t1"), _link("same_source_family_as", "t2")]))
    first = builder.run(root)
    group = _group_of(first, resolved)
    group_id, old_key, size = group.id, group.key, len(group.members)
    _set_identity(root, resolved, "resolved")
    second = builder.run(root)
    after = _group_of(second, member)
    assert after.id == group_id and after.key != old_key and len(after.members) == size - 1
    assert second.retired == [] and [(i, old) for i, old, _ in second.inherited] == [(group_id, old_key)]
    mapping = json.loads((root / IDS_FILE).read_text(encoding="utf-8"))
    assert mapping[after.key] == group_id and old_key not in mapping and len(mapping) == len(first.ids), "no new id was created"
    record = _record(root, group_id)
    assert record["group_key"] == after.key and resolved not in record["members"] and "retired" not in record
    assert record["members"] == sorted(m.id for m in after.members)
    assert re.search(rf"^## {group_id} ", builder.render_markdown(second), re.M), "the heading a person was working from survives"


def test_a_key_that_two_retired_keys_overlap_gets_a_new_id_and_both_are_listed_retired(tmp_path):
    root = _synthetic(tmp_path, _entry("t1", identity="resolved"), _entry("t2", identity="resolved"),
                      _entry("a1", links=[_link("same_source_family_as", "t1")]), _entry("a2", links=[_link("same_source_family_as", "t2")]))
    first = builder.run(root)
    assert (_group_of(first, "a1").id, _group_of(first, "a2").id) == ("IR-001", "IR-002")
    _add_entry(root, _entry("bridge", links=[_link("derived_from", "t1"), _link("derived_from", "t2")]))   # joins both groups
    second = builder.run(root)
    merged = _group_of(second, "bridge")
    assert merged.key == "t1|t2" and {m.id for m in merged.members} == {"a1", "a2", "bridge"} and merged.id == "IR-003"
    assert second.retired == [("IR-001", "t1"), ("IR-002", "t2")] and second.inherited == []
    markdown = builder.render_markdown(second)
    retired = _section(markdown, "Summary")
    assert "IR-001" in retired and "IR-002" in retired and "Retired ids" in retired
    assert [r.get("retired") for r in _read_records(root / QUEUE_FILE)] == [True, True, None]
    assert _record(root, "IR-001")["members"] == ["a1"], "a retired record is left as it was, only flagged"
    assert builder.main(["--root", str(root), "--dry-run"]) == 0


def test_one_retired_key_overlapping_two_new_keys_is_inherited_by_neither(tmp_path):
    root = _synthetic(tmp_path, _entry("t1", identity="resolved"), _entry("t2", identity="resolved"),
                      _entry("bridge", links=[_link("derived_from", "t1"), _link("derived_from", "t2")]),
                      _entry("a1", links=[_link("same_source_family_as", "t1")]), _entry("a2", links=[_link("same_source_family_as", "t2")]))
    first = builder.run(root)
    assert [g.key for g in first.groups] == ["t1|t2"] and first.groups[0].id == "IR-001"
    _set_identity(root, "bridge", "resolved")                       # the one group splits in two
    second = builder.run(root)
    assert {g.key: g.id for g in second.groups} == {"t1": "IR-002", "t2": "IR-003"}
    assert second.retired == [("IR-001", "t1|t2")] and second.inherited == []
    assert len({g.id for g in second.groups}) == len(second.groups), "an id is never shared by two live groups"


def test_a_group_that_loses_all_its_members_is_retired_and_its_open_record_is_flagged(tmp_path):
    root = _synthetic(tmp_path, _entry("t", identity="resolved"), _entry("a1", links=[_link("same_source_family_as", "t")]), _entry("loner"))
    first = builder.run(root)
    gone, kept = _group_of(first, "a1"), _group_of(first, "loner")
    record_before = _record(root, gone.id)
    kept_before = _record(root, kept.id)
    _set_identity(root, "a1", "resolved")
    second = builder.run(root)
    assert second.retired == [(gone.id, gone.key)] and [g.id for g in second.groups] == [kept.id]
    flagged = _record(root, gone.id)
    assert flagged == {**record_before, "retired": True} and flagged["status"] == "open", "flagged, and nothing else changed"
    assert _record(root, kept.id) == kept_before
    assert json.loads((root / IDS_FILE).read_text(encoding="utf-8"))[gone.key] == gone.id, "the id stays reserved"
    _set_identity(root, "a1", "candidate")                          # undone: the group is live again under the same id
    third = builder.run(root)
    assert third.retired == [] and _group_of(third, "a1").id == gone.id
    assert "retired" not in _record(root, gone.id)


# --- the markdown a person reads ----------------------------------------------------------------------------------------

def test_markdown_has_no_absolute_paths_and_no_confidence_language(real_markdown):
    assert builder.INTRO in real_markdown
    assert not ABSOLUTE_PATH.search(real_markdown)
    own_words = "\n".join(line for line in real_markdown.replace(builder.INTRO, "").splitlines() if not line.lstrip().startswith(">"))
    for word in CONFIDENCE_WORDS:
        assert word not in own_words.lower(), word


def test_the_intro_says_these_are_decisions_for_a_person_and_nothing_changes(real_markdown):
    intro = builder.INTRO
    assert "decisions for a person" in intro and "Nothing in this file changes any registry record" in intro
    assert "Recommendations are not acceptance" in intro


def test_every_group_has_one_ir_id_one_decision_and_all_its_members(real_model, real_markdown):
    headings = re.findall(r"^## (IR-\d{3}) ", real_markdown, re.M)
    assert headings == [g.id for g in real_model.groups] and len(headings) == len(set(headings))
    assert real_markdown.count("**Decision needed.**") == len(real_model.groups)
    sections = re.split(r"^(?=## IR-\d{3} )", real_markdown, flags=re.M)[1:]
    assert len(sections) == len(real_model.groups)
    for group, section in zip(real_model.groups, sections):
        for member in group.members:
            assert section.count(f"### `{member.id}`") == 1, member.id
        assert f"`{group.key}`" in section


def test_the_legend_says_the_markdown_is_current_and_the_jsonl_is_a_snapshot_while_open(real_markdown):
    legend = _section(real_markdown, "How to read this")
    assert "work/corpus/identity_review_queue.jsonl" in legend and "work/corpus/review_queue.jsonl" not in legend
    assert "source of truth" in legend and "snapshot" in legend and "status `open`" in legend
    assert "retired: true" in legend


def test_the_summary_says_when_no_id_is_retired(real_model, real_markdown):
    if real_model.retired:
        pytest.skip("this registry has retired ids")
    assert "Retired ids: none." in _section(real_markdown, "Summary")


def test_the_summary_table_lists_every_group_once(real_model, real_markdown):
    summary = _section(real_markdown, "Summary")
    for group in real_model.groups:
        assert len(re.findall(rf"^\| {group.id} \|", summary, re.M)) == 1, group.id
    counts = real_model.blocker_counts
    for kind in ("identity", "access", "unreleased", "source_availability", "adapter"):
        assert f"`{kind}` {counts[kind]}" in summary


def test_markdown_is_deterministic(real_model):
    assert builder.render_markdown(real_model) == builder.render_markdown(builder.build_model(ROOT))


# --- the command ---------------------------------------------------------------------------------------------------------

def test_command_writes_the_report_and_dry_run_writes_nothing(tmp_path, capsys):
    root = _workspace(tmp_path, with_ids=False)
    corpus_before = (root / CORPUS_QUEUE).read_bytes()
    assert builder.main(["--root", str(root), "--dry-run"]) == 0
    assert not (root / "reports/identity_review_queue.md").exists() and not (root / IDS_FILE).exists()
    assert not (root / QUEUE_FILE).exists() and (root / CORPUS_QUEUE).read_bytes() == corpus_before
    assert builder.main(["--root", str(root)]) == 0
    report = (root / "reports/identity_review_queue.md").read_text(encoding="utf-8")
    assert report.startswith("# Identity review queue") and report.endswith("\n")
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["groups"] == len(re.findall(r"^## IR-\d{3} ", report, re.M))
