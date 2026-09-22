import pytest

from dataset_atlas.exports.publication import _public_dataset, PublicationError
from dataset_atlas.models import Dataset


def test_relationship_navigation_preserves_scope_without_private_receipts():
    entry = Dataset(id='toy', name='Toy', release='r1', snapshot_id='s1', relationships=[
        {'type': 'same_source_family_as', 'target_id': 'coco', 'scope': 'Release identity not established', 'evidence_ids': ['private-receipt'], 'excerpt': 'private paper text'},
        {'type': 'alias', 'alias_id': 'old', 'reason': 'private evidence'},
    ])
    public = _public_dataset(entry)
    assert public['relationships'] == [{'type': 'same_source_family_as', 'target_id': 'coco', 'scope': 'Release identity not established'}]
    assert public['adapter_config'] == {} and public['evidence'] == []


def test_relationship_public_fields_still_undergo_private_path_scan():
    entry = Dataset(id='toy', name='Toy', release='r1', snapshot_id='s1', relationships=[{'type': 'variant', 'target': '/home/researcher/private'}])
    with pytest.raises(PublicationError):
        _public_dataset(entry)
