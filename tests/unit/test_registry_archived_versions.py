"""Frozen identities remain readable explicitly without entering the current catalogue."""
import json

import pytest
import yaml

from dataset_atlas.models import Dataset
from dataset_atlas.registry import Registry


def _prepared(workspace, dataset, name):
    directory = workspace / 'work/prepared' / dataset.id / name
    directory.mkdir(parents=True)
    (directory / 'dataset.json').write_text(dataset.model_dump_json())
    return directory


def test_removed_card_has_only_explicit_immutable_version_access(workspace, pack):
    frozen = pack.dataset.model_copy(update={'release': 'old-release', 'snapshot_id': 'old-snapshot'})
    directory = _prepared(workspace, frozen, 'old')
    (workspace / 'registry/datasets/fixture.yaml').unlink()
    (workspace / 'work/packs/fixture/pack.json').unlink()
    registry = Registry(workspace)

    assert registry.ids() == [] and registry.datasets() == []
    for lookup in (registry.dataset, registry.baseline_dataset, registry.pack, registry.versions):
        with pytest.raises(KeyError):
            lookup('fixture')
    actual = registry.dataset_version('fixture', 'old-release', 'old-snapshot')
    assert actual.id == 'fixture' and actual.snapshot_id == 'old-snapshot'
    assert registry.versions('fixture', snapshot_id='old-snapshot') == [
        (actual, directory / 'pack/pack.json', directory / 'snapshot')]
    assert registry.ids() == []


def test_baseline_pack_preserves_explicit_version_after_card_removal(workspace, pack):
    (workspace / 'registry/datasets/fixture.yaml').unlink()
    before = (workspace / 'work/packs/fixture/pack.json').read_bytes()
    registry = Registry(workspace)
    actual = registry.dataset_version('fixture', 'r1', 's1')
    assert actual.id == 'fixture' and actual.snapshot_id == 's1'
    assert actual.adapter_config == pack.dataset.adapter_config
    assert (workspace / 'work/packs/fixture/pack.json').read_bytes() == before
    assert registry.versions('fixture', release_id='missing') == []


def test_explicit_identity_does_not_follow_a_current_alias(workspace, pack):
    (workspace / 'registry/datasets/fixture.yaml').unlink()
    current = Dataset(id='current', name='Current', aliases=['fixture'], release='r1', snapshot_id='s1')
    (workspace / 'registry/datasets/current.yaml').write_text(yaml.safe_dump(current.model_dump()))
    registry = Registry(workspace)
    assert registry.dataset('fixture').id == 'current'
    assert registry.dataset_version('fixture', 'r1', 's1').id == 'fixture'
    (workspace / 'work/packs/fixture/pack.json').unlink()
    with pytest.raises(KeyError):
        registry.dataset_version('fixture', 'r1', 's1')


def test_old_baseline_metadata_is_not_rebound_to_a_new_card(workspace, pack):
    current = pack.dataset.model_copy(update={'release': 'new-release', 'snapshot_id': 'new-snapshot'})
    (workspace / 'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(current.model_dump()))
    registry = Registry(workspace)
    assert registry.dataset('fixture').snapshot_id == 'new-snapshot'
    assert registry.dataset_version('fixture', 'r1', 's1').snapshot_id == 's1'


def test_same_release_needs_a_snapshot_when_multiple_snapshots_are_retained(workspace, pack):
    for snapshot in ('old', 'new'):
        _prepared(workspace, pack.dataset.model_copy(update={'release': 'shared', 'snapshot_id': snapshot}), snapshot)
    registry = Registry(workspace)
    with pytest.raises(KeyError, match='snapshot'):
        registry.dataset_version('fixture', 'shared')
    assert registry.dataset_version('fixture', 'shared', 'old').snapshot_id == 'old'


def test_immutable_version_document_must_match_the_requested_dataset(workspace, pack):
    directory = _prepared(workspace, pack.dataset, 'old')
    document = json.loads((directory / 'dataset.json').read_text())
    document['id'] = 'foreign'
    (directory / 'dataset.json').write_text(json.dumps(document))
    with pytest.raises(ValueError, match='identity'):
        Registry(workspace).versions('fixture', snapshot_id='s1')


def test_explicit_history_rejects_path_traversal(workspace):
    with pytest.raises(ValueError, match='Invalid dataset ID'):
        Registry(workspace).versions('../fixture', snapshot_id='s1')


def test_archived_baseline_pack_keeps_the_interactive_size_bound(workspace):
    (workspace / 'registry/datasets/fixture.yaml').unlink()
    with (workspace / 'work/packs/fixture/pack.json').open('r+b') as stream:
        stream.truncate(100_000_001)
    with pytest.raises(ValueError, match='size budget'):
        Registry(workspace).dataset_version('fixture', 'r1', 's1')


def test_snapshot_discovery_includes_archived_ids_only_for_explicit_snapshots(workspace, pack):
    archived = pack.dataset.model_copy(update={'id': 'archived', 'snapshot_id': 'archived-snapshot'})
    _prepared(workspace, archived, 'old')
    registry = Registry(workspace)
    assert registry.ids_for_snapshots(None) == ['fixture']
    assert registry.ids_for_snapshots([]) == ['fixture']
    assert registry.ids_for_snapshots(['archived-snapshot']) == ['archived']
    assert registry.ids_for_snapshots(['s1', 'archived-snapshot']) == ['archived', 'fixture']
    assert registry.ids() == ['fixture']


def test_snapshot_discovery_reads_frozen_baseline_metadata_without_parsing_records(workspace, monkeypatch):
    (workspace / 'registry/datasets/fixture.yaml').unlink()
    from dataset_atlas.models import Pack
    def no_record_parse(*args, **kwargs):
        raise AssertionError('Snapshot discovery must not construct record models')
    monkeypatch.setattr(Pack, 'model_validate_json', no_record_parse)
    registry = Registry(workspace)
    assert registry.ids_for_snapshots(['s1']) == ['fixture']
    assert registry.dataset_version('fixture', 'r1', 's1').id == 'fixture'
    assert registry.ids() == []


def test_snapshot_discovery_accepts_manifest_metadata_without_a_catalogue_card(workspace):
    (workspace / 'registry/datasets/fixture.yaml').unlink()
    (workspace / 'work/packs/fixture/pack.json').unlink()
    directory = workspace / 'work/snapshots/fixture'
    directory.mkdir(parents=True)
    (directory / 'manifest.json').write_text(json.dumps({'dataset_id': 'fixture', 'snapshot_id': 'frozen'}))
    assert Registry(workspace).ids_for_snapshots(['frozen']) == ['fixture']


def test_snapshot_discovery_refreshes_changed_metadata(workspace, pack):
    directory = _prepared(workspace, pack.dataset.model_copy(update={'snapshot_id': 'old'}), 'v1')
    registry = Registry(workspace)
    assert registry.ids_for_snapshots(['old']) == ['fixture']
    document = json.loads((directory / 'dataset.json').read_text())
    document['snapshot_id'] = 'new'
    (directory / 'dataset.json').write_text(json.dumps(document))
    registry.refresh()
    assert registry.ids_for_snapshots(['old']) == []
    assert registry.ids_for_snapshots(['new']) == ['fixture']


def test_snapshot_ids_are_compared_as_values_and_never_used_as_paths(workspace):
    registry = Registry(workspace)
    assert registry.ids_for_snapshots(['../../outside', '/tmp/manifest.json', '*']) == []
    with pytest.raises(ValueError, match='collection'):
        registry.ids_for_snapshots('s1')


def test_frozen_header_lookup_handles_top_level_field_order(workspace):
    path = workspace / 'work/packs/fixture/pack.json'
    document = json.loads(path.read_text())
    path.write_text(json.dumps({'records': document['records'], 'dataset': document['dataset'],
                               **{k:v for k,v in document.items() if k not in {'records', 'dataset'}}}))
    (workspace / 'registry/datasets/fixture.yaml').unlink()
    assert Registry(workspace).ids_for_snapshots(['s1']) == ['fixture']


def test_legacy_storage_variant_uses_frozen_metadata_identity_without_aliasing(workspace):
    original = workspace / 'work/packs/fixture'
    variant = workspace / 'work/packs/storage-variant'
    original.rename(variant)
    (workspace / 'registry/datasets/fixture.yaml').unlink()
    snapshot = workspace / 'work/snapshots/storage-variant'
    snapshot.mkdir(parents=True)
    (snapshot / 'manifest.json').write_text(json.dumps({'dataset_id': 'fixture', 'snapshot_id': 's1'}))
    registry = Registry(workspace)
    assert registry.ids_for_snapshots(['s1']) == ['fixture']
    versions = registry.versions('fixture', release_id='r1', snapshot_id='s1')
    assert [(d.id,p,s) for d,p,s in versions] == [('fixture', variant / 'pack.json', snapshot)]
    assert registry.dataset_version('fixture', 'r1', 's1').id == 'fixture'
    assert registry.ids() == []
    with pytest.raises(ValueError, match='identity'):
        registry.dataset_version('storage-variant', 'r1', 's1')


def test_replaced_metadata_invalidates_cached_identity_even_when_size_and_mtime_match(workspace, pack):
    import os
    directory = _prepared(workspace, pack.dataset.model_copy(update={'snapshot_id': 'old'}), 'v1')
    path = directory / 'dataset.json'
    registry = Registry(workspace)
    assert registry.ids_for_snapshots(['old']) == ['fixture']
    assert registry.versions('fixture', snapshot_id='old')
    before = path.stat()
    replacement = path.with_suffix('.replacement')
    replacement.write_text(path.read_text().replace('"snapshot_id":"old"', '"snapshot_id":"new"'))
    os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
    replacement.replace(path)
    assert path.stat().st_size == before.st_size
    registry.refresh()
    assert registry.ids_for_snapshots(['old']) == []
    assert registry.versions('fixture', snapshot_id='old') == []
    assert registry.ids_for_snapshots(['new']) == ['fixture']


def test_current_baseline_supplies_source_config_for_same_sanitized_frozen_identity(workspace, pack):
    current = pack.dataset.model_copy(update={'adapter':'structured_archive',
        'adapter_config':{'path':'work/native/source.json', 'sha256':'a' * 64},
        'description':'Current catalogue description', 'rights':{'records':'current-policy'}})
    (workspace / 'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(current.model_dump()))
    registry = Registry(workspace)
    frozen = registry.dataset_version('fixture', 'r1', 's1')
    assert frozen.adapter == 'structured_archive'
    assert frozen.adapter_config == {'path':str(workspace / 'work/native/source.json'), 'sha256':'a' * 64}
    assert frozen.description == pack.dataset.description
    assert frozen.rights == pack.dataset.rights


@pytest.mark.parametrize('changed', [{'release':'new-release'}, {'snapshot_id':'new-snapshot'}])
def test_current_source_config_never_fills_a_different_frozen_binding(workspace, pack, changed):
    current = pack.dataset.model_copy(update={**changed, 'adapter':'structured_archive',
                                             'adapter_config':{'path':'work/native/other.json'}})
    (workspace / 'registry/datasets/fixture.yaml').write_text(yaml.safe_dump(current.model_dump()))
    frozen = Registry(workspace).dataset_version('fixture', 'r1', 's1')
    assert frozen.adapter == pack.dataset.adapter
    assert frozen.adapter_config == {}
