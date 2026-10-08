"""Appending to a registry list edits the text in place instead of re-dumping the document.

A plain `yaml.safe_dump` re-flows long scalars, so 20 of the 333 registry files do not round-trip byte-for-byte at
any wrap width; an evidence refresh must leave every other line of those files alone.
"""
import difflib
from pathlib import Path

import pytest
import yaml

from dataset_atlas.registry.yaml_edit import append_list_items

DOCUMENT = """\
schema_version: '1.0'
id: demo
description: A long description that PyYAML would wrap differently if the whole document were dumped
  again, which is exactly the diff noise a refresh must not create.
coverage:
  access: public
  blockers:
  - First blocker
    continued on a second line.
  - Second blocker
  preview_count: 0
evidence:
- kind: corpus_mention
  excerpt: a quoted passage
    that wraps
  page: 3
- kind: source_audit_access
  checked_on: '2026-09-22'
source_url: https://example.org/demo
modalities:
- image
"""


def _only_insertions(before: str, after: str) -> bool:
    matcher = difflib.SequenceMatcher(a=before.splitlines(), b=after.splitlines(), autojunk=False)
    return all(tag in ("equal", "insert") for tag, *_ in matcher.get_opcodes())


def test_a_new_evidence_item_lands_at_the_end_of_the_evidence_block_and_nothing_else_changes():
    item = {"kind": "source_audit_refresh", "url": "https://example.org/demo", "checked_on": "2026-10-08", "note": "n"}
    edited = append_list_items(DOCUMENT, ("evidence",), [item])
    assert _only_insertions(DOCUMENT, edited)
    assert edited.index("checked_on: '2026-09-22'") < edited.index("- kind: source_audit_refresh") < edited.index("source_url:")
    assert yaml.safe_load(edited)["evidence"][-1] == item
    assert yaml.safe_load(edited)["modalities"] == ["image"]


def test_a_nested_block_list_is_extended_after_its_continuation_lines_at_the_items_own_indent():
    edited = append_list_items(DOCUMENT, ("coverage", "blockers"), ["Third blocker, observed 2026-10-08"])
    lines = edited.splitlines()
    position = lines.index("  - Second blocker")
    assert lines[position + 1] == "  - Third blocker, observed 2026-10-08"
    assert lines[position + 2] == "  preview_count: 0"
    assert yaml.safe_load(edited)["coverage"]["blockers"][-1] == "Third blocker, observed 2026-10-08"


def test_a_list_that_ends_the_file_is_extended_without_a_missing_newline():
    edited = append_list_items(DOCUMENT, ("modalities",), ["text"])
    assert edited.endswith("- image\n- text\n")


def test_every_original_line_survives_in_order_for_each_target():
    for path, items in ((("evidence",), [{"kind": "x"}]), (("coverage", "blockers"), ["b"]), (("modalities",), ["text"])):
        assert _only_insertions(DOCUMENT, append_list_items(DOCUMENT, path, items))


def test_an_empty_flow_list_becomes_a_block_list_in_the_files_own_style():
    text = "id: demo\ncoverage:\n  access: public\n  blockers: []\n  unit: example\n"
    edited = append_list_items(text, ("coverage", "blockers"), ["A gate"])
    assert edited == "id: demo\ncoverage:\n  access: public\n  blockers:\n  - A gate\n  unit: example\n"


def test_strings_that_need_quoting_survive_the_round_trip():
    item = {"kind": "source_audit_refresh", "note": "x: y # not a comment, 'quoted' \"double\"", "http_status": None}
    assert yaml.safe_load(append_list_items(DOCUMENT, ("evidence",), [item]))["evidence"][-1] == item


def test_a_long_note_is_wrapped_inside_the_item_without_leaving_it():
    item = {"kind": "source_audit_refresh", "note": "word " * 80}
    edited = append_list_items(DOCUMENT, ("evidence",), [item])
    assert yaml.safe_load(edited)["evidence"][-1]["note"] == item["note"]
    assert yaml.safe_load(edited)["source_url"] == "https://example.org/demo"


def test_a_missing_key_is_refused():
    with pytest.raises(KeyError):
        append_list_items(DOCUMENT, ("coverage", "gates"), ["x"])
    with pytest.raises(KeyError):
        append_list_items(DOCUMENT, ("rights",), ["x"])


def test_a_non_list_target_is_refused_rather_than_rewritten():
    with pytest.raises(ValueError):
        append_list_items(DOCUMENT, ("coverage", "access"), ["x"])


def test_a_flow_list_with_items_is_refused_rather_than_guessed():
    with pytest.raises(ValueError):
        append_list_items("id: demo\nevidence: [a, b]\n", ("evidence",), ["c"])


def test_nothing_to_append_returns_the_text_unchanged():
    assert append_list_items(DOCUMENT, ("evidence",), []) == DOCUMENT


def test_every_shipped_registry_file_accepts_an_evidence_append_as_a_pure_insertion():
    files = sorted((Path(__file__).resolve().parents[2] / "registry/datasets").glob("*.yaml"))
    assert len(files) > 300
    for path in files:
        original = path.read_text()
        edited = append_list_items(original, ("evidence",), [{"kind": "source_audit_refresh", "note": "probe " * 40}])
        assert _only_insertions(original, edited), path.name
