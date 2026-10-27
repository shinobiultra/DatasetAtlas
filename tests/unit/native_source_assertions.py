"""Current native acceptance checks; no historical report or network access."""
import hashlib
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

from dataset_atlas.queries.parquet import ParquetSnapshot


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def assert_current_native_source(registry, dataset, pack, count):
    """Check retained source pins and exact preview membership in its full index.

    Callers skip only if their primary acquisition is absent. Once it is present,
    missing pinned originals or an inconsistent snapshot are acceptance failures.
    Boolean envelope comparisons keep native values out of pytest failure output.
    """
    root = registry.root
    source = Path(dataset.adapter_config['path'])
    assert sha256(source) == dataset.adapter_config['sha256']
    assert dataset.coverage.total_count == count
    snapshot = ParquetSnapshot(root, registry.snapshot_path(dataset.id))
    assert (snapshot.dataset_id, snapshot.release_id, snapshot.snapshot_id) == (
        dataset.id, dataset.release, dataset.snapshot_id)
    assert snapshot.population_scope == 'complete' and snapshot.record_count == count
    canonical = snapshot.records([record.id for record in pack.records])
    assert len(canonical) == len(pack.records)
    same_envelopes = all(
        (canonical[record.id].source, canonical[record.id].text,
         canonical[record.id].question, canonical[record.id].choices,
         canonical[record.id].asset_ids, canonical[record.id].snapshot_id)
        == (record.source, record.text, record.question, record.choices,
            record.asset_ids, dataset.snapshot_id)
        for record in pack.records)
    assert same_envelopes, 'Preview records differ from their current complete native snapshot'
    recipe = root / 'registry/recipes' / (dataset.id + '.yaml')
    if not recipe.is_file():
        return
    document = yaml.safe_load(recipe.read_text())
    assert document['expected_count'] == count
    source_roots = [root / 'work/sources' / dataset.id]
    if dataset.adapter_config.get('media_root'):
        source_roots.append(Path(dataset.adapter_config['media_root']))
    for entry in document['files']:
        names = {Path(entry['source_name']).name,
                 Path(unquote(urlsplit(entry['url']).path)).name}
        candidates = {path for directory in source_roots if directory.is_dir()
                      for name in names for path in directory.rglob(name) if path.is_file()}
        matches_pin = any(path.stat().st_size == entry['bytes'] and sha256(path) == entry['sha256']
                          for path in candidates)
        assert matches_pin, 'A retained native recipe input is absent or differs from its pinned bytes'
