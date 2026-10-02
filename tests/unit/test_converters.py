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


# ---- each converter's rule, on small synthetic inputs --------------------------------------------

def convert(name, params, inputs, tmp_path):
    from dataset_atlas.converters import CONVERTERS, text  # noqa: F401
    result = CONVERTERS[name](params, inputs, tmp_path / name, lambda: None)
    path = result['path']
    return [json.loads(line) for line in path.read_text().splitlines()], result


def test_anthropic_gz_json_array_gets_a_one_based_source_row_and_keeps_native_types(tmp_path):
    import gzip
    source = tmp_path / 'r.jsonl.gz'
    with gzip.open(source, 'wt') as stream:
        json.dump([{'rating': 0.0, 'tags': None, 'is_upworker': False}, {'rating': 3.0, 'tags': ['x'], 'is_upworker': True}], stream)
    rows, _ = convert('anthropic_red_team', {}, {'source_gz': source}, tmp_path)
    assert rows == [{'rating': 0.0, 'tags': None, 'is_upworker': False, 'source_row': 1},
                    {'rating': 3.0, 'tags': ['x'], 'is_upworker': True, 'source_row': 2}]


def test_maliciousinstruct_skips_blank_lines_but_keeps_true_line_numbers(tmp_path):
    source = tmp_path / 'm.txt'
    source.write_text('first\n\nthird\n')
    rows, _ = convert('maliciousinstruct', {}, {'source_txt': source}, tmp_path)
    assert rows == [{'source_line': 1, 'prompt': 'first'}, {'source_line': 3, 'prompt': 'third'}]


def test_tdc2023_numbers_dev_then_test_behaviours(tmp_path):
    (tmp_path / 'd.json').write_text('["a", "b"]')
    (tmp_path / 't.json').write_text('["c"]')
    rows, _ = convert('tdc2023', {}, {'dev_behaviors': tmp_path / 'd.json', 'test_behaviors': tmp_path / 't.json'}, tmp_path)
    assert [(r['source_id'], r['split'], r['source_index'], r['behavior']) for r in rows] == [('dev:1', 'dev', 1, 'a'), ('dev:2', 'dev', 2, 'b'), ('test:1', 'test', 1, 'c')]


def test_bbq_adds_category_scoped_ids_and_choices_and_preserves_every_original_field(tmp_path):
    for category, answers in (('Age', 'x'), ('SES', 'y')):
        (tmp_path / f'{category}.jsonl').write_text(json.dumps({'example_id': 0, 'ans0': answers + '0', 'ans1': answers + '1', 'ans2': answers + '2', 'label': 1}) + '\n\n'
                                                      + json.dumps({'example_id': 1, 'ans0': 'a', 'ans1': 'b', 'ans2': 'c', 'label': 0}) + '\n')
    rows, _ = convert('bbq', {'categories': ['SES', 'Age']}, {c: tmp_path / f'{c}.jsonl' for c in ('Age', 'SES')}, tmp_path)
    assert [r['source_id'] for r in rows] == ['SES:0', 'SES:2', 'Age:0', 'Age:2']  # the id is the file line, so a blank line leaves a gap
    assert rows[0]['choices'] == ['y0', 'y1', 'y2'] and rows[0]['label'] == 1 and rows[0]['example_id'] == 0


def test_halueval_shows_the_task_specific_field_and_numbers_rows_per_task(tmp_path):
    inputs = {}
    for task, shown in (('dialogue', 'dialogue_history'), ('general', 'user_query'), ('qa', 'question'), ('summarization', 'document')):
        path = tmp_path / f'{task}.json'
        path.write_text(json.dumps({shown: f'{task} text', 'other': 1}) + '\n')
        inputs[task] = path
    rows, _ = convert('halueval', {}, inputs, tmp_path)
    assert [(r['task'], r['source_id'], r['source_row'], r['display_text']) for r in rows] == [
        ('dialogue', 'dialogue:1', 1, 'dialogue text'), ('general', 'general:1', 1, 'general text'),
        ('qa', 'qa:1', 1, 'qa text'), ('summarization', 'summarization:1', 1, 'summarization text')]


def test_behonest_interleaves_files_row_by_row_so_any_prefix_spans_every_scenario(tmp_path):
    members = [{'key': 'a', 'member': 'Alpha/one.json'}, {'key': 'b', 'member': 'Beta/two.json'}]
    (tmp_path / 'a.json').write_text(json.dumps([{'id': 1, 'prompt': 'a1'}, {'id': 2, 'prompt': 'a2'}, {'id': 3, 'prompt': 'a3'}]))
    (tmp_path / 'b.json').write_text(json.dumps([{'id': 1, 'prompt_1': 'b1'}]))
    rows, _ = convert('behonest', {'members': members}, {'a': tmp_path / 'a.json', 'b': tmp_path / 'b.json'}, tmp_path)
    assert [r['source_id'] for r in rows] == ['Alpha/one.json::1', 'Beta/two.json::1', 'Alpha/one.json::2', 'Alpha/one.json::3']
    assert [r['display_text'] for r in rows] == ['a1', 'b1', 'a2', 'a3']  # `prompt_1` is shown when there is no `prompt`
    assert rows[1]['scenario'] == 'Beta' and rows[1]['source_member'] == 'Beta/two.json'


def test_glue_sst2_keeps_typed_columns_and_null_test_labels(tmp_path):
    import pyarrow.parquet as pq
    from dataset_atlas.converters import text
    counts = {'train': 67349, 'dev': 872, 'test': 1821}
    source = tmp_path / 'SST-2.zip'
    with zipfile.ZipFile(source, 'w') as z:
        z.writestr('SST-2/train.tsv', 'sentence\tlabel\n' + ''.join(f'train {i}\t{i % 2}\n' for i in range(counts['train'])))
        z.writestr('SST-2/dev.tsv', 'sentence\tlabel\n' + ''.join(f'dev {i}\t1\n' for i in range(counts['dev'])))
        z.writestr('SST-2/test.tsv', 'index\tsentence\n' + ''.join(f'{i}\ttest {i}\n' for i in range(counts['test'])))
    result = text.glue_sst2({}, {'source_zip': source}, tmp_path / 'o', lambda: None)
    table = pq.read_table(result['path'])
    assert table.schema.field('label').type == 'int8' and table.schema.field('source_index').type == 'int32'
    assert result['count'] == sum(counts.values())
    last = table.slice(table.num_rows - 1, 1).to_pylist()[0]
    assert last['label'] is None and last['label_status'] == 'withheld_by_glue' and last['split'] == 'test'


def test_pope_joins_each_question_to_its_coco_val2014_image_and_keeps_question_ids_numeric(tmp_path):
    inputs = {}
    for number, strategy in enumerate(('adversarial', 'popular', 'random'), 1):
        path = tmp_path / f'{strategy}.json'
        path.write_text(json.dumps({'question_id': number, 'image': f'COCO_val2014_{number:012d}.jpg', 'text': 'Is there a cat in the image?', 'label': 'yes'}) + '\n')
        inputs[strategy] = path
    rows, _ = convert('pope', {}, inputs, tmp_path)
    assert [(r['source_id'], r['question_id'], r['media_path']) for r in rows] == [
        ('adversarial:1', 1, 'val2014/COCO_val2014_000000000001.jpg'), ('popular:2', 2, 'val2014/COCO_val2014_000000000002.jpg'),
        ('random:3', 3, 'val2014/COCO_val2014_000000000003.jpg')]
    assert rows[0]['question'] == 'Is there a cat in the image?' and rows[0]['label'] == 'yes' and rows[0]['strategy'] == 'adversarial'


# ---- converters that extract media ---------------------------------------------------------

def test_media_converters_pin_their_extracted_files_and_set_media_root_for_the_adapter(tmp_path, monkeypatch):
    from dataset_atlas.converters import CONVERTERS, media_digest, write_rows
    def extract(params, inputs, output_dir, check):
        media = output_dir / 'media'
        media.mkdir(parents=True)
        (media / 'a.png').write_bytes(b'png-a')
        result = write_rows(lambda: iter([{'id': 'a', 'image': 'a.png'}]), output_dir / 'records.jsonl', 'jsonl', check)
        return {**result, 'media_dir': media}
    monkeypatch.setitem(CONVERTERS, 'fake_media', extract)
    first = CONVERTERS['fake_media']({}, {}, tmp_path / 'probe', lambda: None)
    spec = {'name': 'fake_media', 'count': 1, 'rows_sha256': first['rows_sha256'], 'media_sha256': media_digest(first['media_dir'])}
    ok = run_conversion(spec, {}, tmp_path / 'ok')
    assert ok['media_dir'] == tmp_path / 'ok' / 'media'
    with pytest.raises(ValueError, match='Extracted media differ'):
        run_conversion({**spec, 'media_sha256': '0' * 64}, {}, tmp_path / 'bad')


def test_a_recipe_that_pins_media_for_a_converter_without_any_is_refused(tmp_path):
    from dataset_atlas.converters import text  # noqa: F401
    (tmp_path / 'd.json').write_text('["a"]')
    (tmp_path / 't.json').write_text('["b"]')
    inputs = {'dev_behaviors': tmp_path / 'd.json', 'test_behaviors': tmp_path / 't.json'}
    spec = spec_for_tdc(inputs, tmp_path)
    with pytest.raises(ValueError, match='produced none'):
        run_conversion({**spec, 'media_sha256': '1' * 64}, inputs, tmp_path / 'o')


def spec_for_tdc(inputs, tmp_path):
    from dataset_atlas.converters import text
    produced = text.tdc2023({}, inputs, tmp_path / 'p', lambda: None)
    return {'name': 'tdc2023', 'count': produced['count'], 'rows_sha256': produced['rows_sha256']}
