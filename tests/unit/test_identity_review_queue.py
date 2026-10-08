"""scripts/build_identity_review_queue.py turns unresolved catalogue identities into decisions for a person.

The queue is read-only over the registry: it never edits an entry, never changes `coverage.identity`, `release`, `preview`
or any other field, and never presents a family link as coverage. Only a person changes an identity.

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
QUEUE_FILE = "work/corpus/review_queue.jsonl"
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
    """A throwaway copy of the inputs: registry entries, coverage CSV, the committed id mapping and the review queue."""
    shutil.copytree(ROOT / "registry/datasets", tmp_path / "registry/datasets")
    (tmp_path / "reports").mkdir()
    shutil.copy(ROOT / "reports/dataset_coverage.csv", tmp_path / "reports/dataset_coverage.csv")
    if with_ids and (ROOT / IDS_FILE).exists():
        shutil.copy(ROOT / IDS_FILE, tmp_path / IDS_FILE)
    (tmp_path / "work/corpus").mkdir(parents=True)
    lines = [json.dumps({"kind": "extraction_quality", "paper_id": f"paper-{n}", "status": "reviewed"}) for n in range(3)]
    if (ROOT / QUEUE_FILE).exists():     # the corpus review items as they are, without any decision this builder already appended
        lines = [line for line in (ROOT / QUEUE_FILE).read_text(encoding="utf-8").splitlines()
                 if line.strip() and json.loads(line).get("kind") != "identity_decision"]
    (tmp_path / QUEUE_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
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
            writer = csv.DictWriter(stream, fieldnames=["dataset_id", "identity", "access", "adapter", "preview"], lineterminator="\n")
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
    assert {key: after[key] for key in before} == before
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
    assert any("|" in key for key in before), "the registry has linked families"
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
    assert _dataset_row("ms-coco")["preview"] == "none"
    assert _real_registry()["ms-coco"]["coverage"]["preview"] == "none"
    member = _member(real_model, "ms-coco")
    assert member.preview == "none"
    group = _group_of(real_model, "ms-coco")
    coco = next(target for target in group.targets if target.id == "coco")
    assert coco.preview == _dataset_row("coco")["preview"], "the family's own state is shown as it is"
    assert any(link.target == "coco" for link in member.links)
    found = re.search(r"^### `ms-coco`.*?(?=^### |^## |\Z)", real_markdown, re.M | re.S)
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


# --- the review queue file ----------------------------------------------------------------------------------------------

def test_queue_records_are_appended_once_and_existing_lines_are_untouched(tmp_path):
    root = _workspace(tmp_path, with_ids=False)
    queue = root / QUEUE_FILE
    before = queue.read_bytes()
    first = builder.run(root)
    after = queue.read_bytes()
    assert after.startswith(before), "existing lines are neither rewritten nor reordered"
    records = [json.loads(line) for line in after[len(before):].decode("utf-8").splitlines()]
    assert len(records) == len(first.groups)
    for record, group in zip(records, first.groups):
        assert list(record) == ["kind", "id", "group_key", "members", "status", "options", "created_by"]
        assert record == {"kind": "identity_decision", "id": group.id, "group_key": group.key,
                          "members": sorted(m.id for m in group.members), "status": "open", "options": group.options,
                          "created_by": "build_identity_review_queue.py"}
    assert len({r["id"] for r in records}) == len(records)
    builder.run(root)
    assert queue.read_bytes() == after, "a second run appends nothing"
    all_ids = [json.loads(line).get("id") for line in queue.read_text(encoding="utf-8").splitlines()]
    assert len([i for i in all_ids if i and i.startswith("IR-")]) == len(set(i for i in all_ids if i and i.startswith("IR-")))


def test_a_queue_file_without_a_trailing_newline_is_appended_to_safely(tmp_path):
    root = _workspace(tmp_path, with_ids=False)
    queue = root / QUEUE_FILE
    original = [json.dumps({"kind": "extraction_quality", "paper_id": "paper-x", "status": "pending"}),
                json.dumps({"kind": "extraction_quality", "paper_id": "paper-y", "status": "reviewed"})]
    queue.write_text("\n".join(original), encoding="utf-8")                 # no trailing newline
    model = builder.run(root)
    lines = queue.read_text(encoding="utf-8").splitlines()
    assert lines[:2] == original
    assert len(lines) == 2 + len(model.groups) and all(json.loads(line) for line in lines)


def test_a_queue_file_that_is_not_json_stops_the_run_before_anything_is_written(tmp_path):
    root = _workspace(tmp_path, with_ids=False)
    (root / QUEUE_FILE).write_text("not json\n", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        builder.run(root)
    assert not (root / IDS_FILE).exists() and not (root / "reports/identity_review_queue.md").exists()
    assert (root / QUEUE_FILE).read_text(encoding="utf-8") == "not json\n"


def test_a_missing_queue_file_is_created(tmp_path):
    root = _workspace(tmp_path, with_ids=False)
    (root / QUEUE_FILE).unlink()
    model = builder.run(root)
    assert len((root / QUEUE_FILE).read_text(encoding="utf-8").splitlines()) == len(model.groups)


def test_a_group_already_in_the_queue_is_not_appended_again_even_if_its_members_changed(tmp_path):
    root = _synthetic(tmp_path, _entry("target", identity="resolved"), _entry("alias-1", links=[_link("same_source_family_as", "target")]))
    builder.run(root)
    queue = root / QUEUE_FILE
    first = queue.read_bytes()
    (root / "registry/datasets/alias-2.yaml").write_text(
        yaml.safe_dump(_entry("alias-2", links=[_link("same_source_family_as", "target")])), encoding="utf-8")
    (root / "registry/datasets/other.yaml").write_text(yaml.safe_dump(_entry("other")), encoding="utf-8")
    builder.run(root)
    lines = queue.read_text(encoding="utf-8").splitlines()
    assert queue.read_bytes().startswith(first)
    assert [json.loads(line)["id"] for line in lines] == ["IR-001", "IR-002"], "the grown group keeps IR-001 and is not appended twice"
    assert json.loads(lines[0])["members"] == ["alias-1"], "an existing record is left exactly as it was written"


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
    queue_before = (root / QUEUE_FILE).read_bytes()
    assert builder.main(["--root", str(root), "--dry-run"]) == 0
    assert not (root / "reports/identity_review_queue.md").exists() and not (root / IDS_FILE).exists()
    assert (root / QUEUE_FILE).read_bytes() == queue_before
    assert builder.main(["--root", str(root)]) == 0
    report = (root / "reports/identity_review_queue.md").read_text(encoding="utf-8")
    assert report.startswith("# Identity review queue") and report.endswith("\n")
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["groups"] == len(re.findall(r"^## IR-\d{3} ", report, re.M))
