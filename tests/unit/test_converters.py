"""A conversion recipe reproduces the maintained table from pinned originals, or fails; it never yields something different."""
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
import yaml

from dataset_atlas.converters import RowDigest, digest_existing, run_conversion
from dataset_atlas.models import Coverage, Dataset
from dataset_atlas.preparation import PreparationManager
from dataset_atlas.preparation.worker import run
from dataset_atlas.registry import Registry


def glue_zip(path: Path, cola=True):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('CoLA/train.tsv', 'gj04\t1\t\tOur friends won\'t buy this analysis.\nbc01\t0\t*\tThey drank the pub.\n')
        z.writestr('CoLA/dev.tsv', 'gj04\t1\t\tOne more.\n')
        z.writestr('CoLA/test.tsv', 'index\tsentence\n0\tUnlabeled sentence.\n')
    return path


def spec_for(zip_path: Path, tmp_path: Path):
    """Pin whatever the converter currently produces, as a maintainer would when writing the recipe."""
    from dataset_atlas.converters import text
    produced = text.glue_task({'task': 'CoLA'}, {'source_zip': zip_path}, tmp_path / 'probe', lambda: None)
    return {'name': 'glue_task', 'params': {'task': 'CoLA'}, 'count': produced['count'], 'rows_sha256': produced['rows_sha256']}


def test_row_digest_is_order_and_content_sensitive_but_key_order_insensitive():
    a, b, c = RowDigest(), RowDigest(), RowDigest()
    for row in ({'x': 1, 'y': 'é'}, {'x': 2}):
        a.add(row)
    for row in ({'y': 'é', 'x': 1}, {'x': 2}):
        b.add(row)
    for row in ({'x': 2}, {'x': 1, 'y': 'é'}):
        c.add(row)
    assert a.hexdigest() == b.hexdigest() != c.hexdigest()


def test_a_matching_conversion_is_accepted_and_withheld_labels_stay_null(tmp_path):
    zip_path = glue_zip(tmp_path / 'CoLA.zip')
    spec = spec_for(zip_path, tmp_path)
    result = run_conversion(spec, {'source_zip': zip_path}, tmp_path / 'out')
    rows = digest_existing(result['path'], 'parquet')
    assert rows == {'count': 4, 'rows_sha256': spec['rows_sha256']} and result['format'] == 'parquet'
    import pyarrow.parquet as pq
    table = pq.read_table(result['path']).to_pylist()
    withheld = [r for r in table if r['split'] == 'test']
    assert withheld[0]['label'] is None and withheld[0]['label_status'] == 'withheld_by_glue'
    assert table[0]['source_id'] == 'train:0' and table[0]['display_text'] == "Our friends won't buy this analysis."


def test_changed_originals_fail_the_conversion_instead_of_producing_different_rows(tmp_path):
    zip_path = glue_zip(tmp_path / 'CoLA.zip')
    spec = spec_for(zip_path, tmp_path)
    changed = tmp_path / 'changed.zip'
    with zipfile.ZipFile(changed, 'w') as z:
        z.writestr('CoLA/train.tsv', 'gj04\t1\t\tA different sentence.\nbc01\t0\t*\tThey drank the pub.\n')
        z.writestr('CoLA/dev.tsv', 'gj04\t1\t\tOne more.\n')
        z.writestr('CoLA/test.tsv', 'index\tsentence\n0\tUnlabeled sentence.\n')
    with pytest.raises(ValueError, match='differ from the maintainer'):
        run_conversion(spec, {'source_zip': changed}, tmp_path / 'out2')


def test_a_wrong_row_count_is_refused_before_the_digest_is_compared(tmp_path):
    zip_path = glue_zip(tmp_path / 'CoLA.zip')
    spec = {**spec_for(zip_path, tmp_path), 'count': 99}
    with pytest.raises(ValueError, match='produced 4 rows; the recipe pins 99'):
        run_conversion(spec, {'source_zip': zip_path}, tmp_path / 'out3')


def test_unknown_converters_and_unpinned_recipes_are_refused(tmp_path):
    with pytest.raises(ValueError, match='Unknown converter'):
        run_conversion({'name': 'run_arbitrary_code', 'count': 1, 'rows_sha256': 'x'}, {}, tmp_path)
    with pytest.raises(ValueError, match='must pin rows_sha256'):
        run_conversion({'name': 'glue_task', 'count': 1}, {}, tmp_path)


def test_malformed_source_rows_fail_loudly(tmp_path):
    bad = tmp_path / 'CoLA.zip'
    with zipfile.ZipFile(bad, 'w') as z:
        z.writestr('CoLA/train.tsv', 'gj04\t1\n')  # three columns missing
        z.writestr('CoLA/dev.tsv', '')
        z.writestr('CoLA/test.tsv', 'index\tsentence\n')
    from dataset_atlas.converters import text
    with pytest.raises(ValueError, match='Malformed source row 0'):
        text.glue_task({'task': 'CoLA'}, {'source_zip': bad}, tmp_path / 'o', lambda: None)


# ---- through the real preparation worker ---------------------------------------------------

def workspace(root: Path, bytes_by_name: dict[str, bytes], conversion: dict):
    (root / 'registry/datasets').mkdir(parents=True)
    (root / 'registry/recipes').mkdir(parents=True)
    entry = Dataset(id='converted', name='Converted', release='r0', snapshot_id='s0', adapter='structured',
                    adapter_config={'path': 'work/sources/none.parquet', 'format': 'parquet', 'mapping': {'id': 'source_id', 'text': 'display_text'}},
                    coverage=Coverage(preview_count=1, total_count=4))
    (root / 'registry/datasets/converted.yaml').write_text(yaml.safe_dump(entry.model_dump()))
    data = bytes_by_name['CoLA.zip']
    recipe = {'adapter': 'structured', 'release': 'converted-r1', 'snapshot_id': 'converted-reviewed', 'expected_count': 4, 'scope': 'four rows',
              'adapter_config': {'mapping': {'id': 'source_id', 'text': 'display_text'}}, 'convert': conversion,
              'files': [{'url': 'https://example.org/CoLA.zip', 'source_name': 'CoLA.zip', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                         'format': 'zip', 'config_key': 'source_zip'}]}
    (root / 'registry/recipes/converted.yaml').write_text(yaml.safe_dump(recipe))


def test_worker_converts_pinned_originals_and_indexes_the_result(tmp_path, monkeypatch):
    zip_path = glue_zip(tmp_path / 'src.zip')
    spec = spec_for(zip_path, tmp_path)
    root = tmp_path / 'ws'
    workspace(root, {'CoLA.zip': zip_path.read_bytes()}, spec)
    monkeypatch.setattr('dataset_atlas.storage.HttpsFetcher.fetch', lambda self, url, *a, **k: zip_path)
    manager = PreparationManager(root)
    plan = manager.plan('converted', 10_000_000, 10_000_000)
    assert plan['ready'] and plan['convert'] == spec
    run(root, plan['id'])
    assert manager.status(plan['id'])['status'] == 'completed'
    dataset = Registry(root).dataset('converted')
    assert dataset.snapshot_id == 'converted-reviewed' and dataset.coverage.total_count == 4
    assert {r.source['split'] for r in Registry(root).pack('converted').records} == {'train', 'dev', 'test'}


def test_worker_fails_the_preparation_when_the_conversion_differs(tmp_path, monkeypatch):
    zip_path = glue_zip(tmp_path / 'src.zip')
    spec = {**spec_for(zip_path, tmp_path), 'rows_sha256': '0' * 64}
    root = tmp_path / 'ws'
    workspace(root, {'CoLA.zip': zip_path.read_bytes()}, spec)
    monkeypatch.setattr('dataset_atlas.storage.HttpsFetcher.fetch', lambda self, url, *a, **k: zip_path)
    manager = PreparationManager(root)
    plan = manager.plan('converted', 10_000_000, 10_000_000)
    with pytest.raises(ValueError, match='differ from the maintainer'):
        run(root, plan['id'])
    assert 'differ from the maintainer' in manager.status(plan['id'])['error']
    assert not (root / 'work/prepared/converted/active.json').exists()


def test_a_conversion_recipe_must_pin_its_digest_at_plan_time(tmp_path):
    zip_path = glue_zip(tmp_path / 'src.zip')
    workspace(tmp_path / 'ws', {'CoLA.zip': zip_path.read_bytes()}, {'name': 'glue_task', 'count': 4, 'rows_sha256': 'not-a-digest'})
    with pytest.raises(ValueError, match='SHA-256 row digest'):
        PreparationManager(tmp_path / 'ws').plan('converted', 10_000_000, 10_000_000)
