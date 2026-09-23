import os
from dataset_atlas.storage.usage import workspace_usage


def test_usage_counts_hardlinks_once_and_does_not_follow_external_links(tmp_path):
    root = tmp_path / 'atlas'; root.mkdir()
    sources = root / 'work/sources'; sources.mkdir(parents=True)
    data = sources / 'original'; data.write_bytes(b'x' * 10000)
    prepared = root / 'work/prepared'; prepared.mkdir()
    os.link(data, prepared / 'copy')
    external = tmp_path / 'corpus'; external.mkdir()
    (external / 'read-only-original').write_bytes(b'z' * 100000)
    (root / 'corpus-link').symlink_to(external, target_is_directory=True)
    report = workspace_usage(root, target_bytes=1, ceiling_bytes=2)
    assert report['logical_bytes'] == 20000
    assert report['unique_file_bytes'] == 10000
    assert report['allocated_bytes'] == data.stat().st_blocks * 512
    assert report['external_symlinks_not_counted'] == 1
    assert report['status'] == 'above_ceiling'
    with_models = workspace_usage(root, extra_roots=[external])
    assert with_models['unique_file_bytes'] == 110000
    assert with_models['included_external_roots'] == [str(external)]
    assert workspace_usage(root, extra_roots=[tmp_path/'missing'])['status'] == 'incomplete_scan'
