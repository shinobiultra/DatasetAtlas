"""The shipped catalogue's relationship links must point at catalogue entries, and reviewed family links must say what they do not establish."""
from pathlib import Path

from dataset_atlas.registry import Registry

ROOT = Path(__file__).resolve().parents[2]


def test_every_relationship_target_id_resolves_to_a_catalogue_entry():
    registry = Registry(ROOT)
    ids = set(registry.ids())
    dangling = [(d.id, rel['type'], rel['target_id']) for d in registry.datasets() for rel in d.relationships
                if isinstance(rel, dict) and rel.get('target_id') and registry.resolve(rel['target_id']) not in ids]
    assert dangling == []


def test_family_links_added_in_review_carry_a_scope_statement_and_check_date():
    registry = Registry(ROOT)
    reviewed = [(d.id, rel) for d in registry.datasets() for rel in d.relationships
                if isinstance(rel, dict) and rel.get('checked_on') == '2026-10-06' and rel.get('status') == 'asserted_from_source_review']
    assert len(reviewed) >= 1  # most reviewed family links sat on removed alias, view and unresolved entries (2026-10-09)
    for entry, rel in reviewed:
        assert rel['type'] in {'same_source_family_as', 'derived_from'}, (entry, rel)
        assert len(rel.get('scope', '')) > 40, (entry, rel)  # a link must say what it does not establish
