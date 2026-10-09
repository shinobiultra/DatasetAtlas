"""Media-benchmark converters (converters/media.py) on small synthetic inputs: each documents one rule of the maintained table."""
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from dataset_atlas.converters import CONVERTERS, digest_existing, media_digest, run_conversion
from dataset_atlas.converters import media

PNG = b'\x89PNG\r\n\x1a\n'
JPG = b'\xff\xd8\xff\xe0'


def png(tag: str) -> bytes:
    return PNG + tag.encode()


def jpg(tag: str) -> bytes:
    return JPG + tag.encode()


def pin(name, params, inputs, tmp_path, **extra):
    """Pin whatever the converter produces, as a maintainer would when writing the recipe."""
    produced = CONVERTERS[name](params, inputs, tmp_path / 'probe', lambda: None)
    spec = {'name': name, 'params': params, 'count': produced['count'], 'rows_sha256': produced['rows_sha256'], **extra}
    if produced.get('media_dir') is not None:
        spec['media_sha256'] = media_digest(produced['media_dir'])
    return spec


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def test_converters_are_registered_by_running_a_conversion():
    for name in ('whoops', 'llava_bench', 'mm_vet', 'illusionvqa', 'jailbreakv_28k', 'omnisafebench_mm'):
        assert name in CONVERTERS


def test_image_extension_is_judged_from_the_signature_and_unknown_encodings_are_refused():
    assert media.image_extension(PNG + b'x') == '.png' and media.image_extension(JPG + b'x') == '.jpg'
    assert media.image_extension(b'RIFF\x00\x00\x00\x00WEBPVP8 ') == '.webp'
    with pytest.raises(ValueError, match='Unsupported source image'):
        media.image_extension(b'GIF89a')
    with pytest.raises(ValueError, match='empty or exceeds'):
        media.checked_image(b'')


def test_unsafe_media_names_and_colliding_stores_are_refused(tmp_path):
    for name in ('', '..', 'a/b.png', '../x.png'):
        with pytest.raises(ValueError, match='Unsafe media file name'):
            media.safe_name(name)
    media.store_image(tmp_path, 'images/a.png', png('1'))
    media.store_image(tmp_path, 'images/a.png', png('1'))  # the same bytes again is fine
    with pytest.raises(ValueError, match='collision'):
        media.store_image(tmp_path, 'images/a.png', png('2'))


# ---- WHOOPS! ---------------------------------------------------------------------------------------------------

def whoops_inputs(tmp_path, second=None):
    first, second = png('first'), second or png('second')
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['image_id', 'selected_caption', 'crowd_captions', 'crowd_explanations', 'crowd_underspecified_captions', 'question_answering_pairs', 'commonsense_category'])
    writer.writerow(['img-a', 'A baby eating a chili', json.dumps(['one', 'two']), json.dumps(['why']), json.dumps(['vague']), json.dumps([['Who?', 'A baby']]), 'Age mismatch'])
    writer.writerow(['img-b', 'Café at noon', json.dumps(['x']), json.dumps(['y']), json.dumps(['z']), json.dumps([]), 'Other'])
    csv_path = tmp_path / 'whoops.csv'
    csv_path.write_bytes(b'\xef\xbb\xbf' + buffer.getvalue().encode())  # the release CSV carries a UTF-8 BOM
    zip_path = tmp_path / 'whoops.zip'
    with zipfile.ZipFile(zip_path, 'w') as z:
        z.writestr('whoops_images/', b'')
        z.writestr('__MACOSX/._whoops_images', b'junk')
        z.writestr('whoops_images/img-a.png', first)
        z.writestr('__MACOSX/whoops_images/._img-a.png', b'junk')
        z.writestr('whoops_images/img-b.png', second)
    return {'source_csv': csv_path, 'source_zip': zip_path}, first, second


def test_whoops_parses_list_columns_and_stores_each_image_by_content_hash_unchanged(tmp_path):
    inputs, first, second = whoops_inputs(tmp_path)
    result = CONVERTERS['whoops']({'images': 2}, inputs, tmp_path / 'out', lambda: None)
    rows = read_jsonl(result['path'])
    assert [r['image_id'] for r in rows] == ['img-a', 'img-b'] and result['count'] == 2
    assert rows[0]['crowd_captions'] == ['one', 'two'] and rows[0]['question_answering_pairs'] == [['Who?', 'A baby']] and rows[1]['question_answering_pairs'] == []
    digest = hashlib.sha256(first).hexdigest()
    assert rows[0]['image_sha256'] == digest and rows[0]['media_path'] == f'images/{digest}.png' and rows[0]['source_image_name'] == 'img-a.png'
    assert (result['media_dir'] / rows[0]['media_path']).read_bytes() == first
    assert (result['media_dir'] / rows[1]['media_path']).read_bytes() == second
    assert sorted(p.name for p in (result['media_dir'] / 'images').iterdir()) == sorted([f'{digest}.png', f"{hashlib.sha256(second).hexdigest()}.png"])


def test_whoops_conversion_pins_rows_and_extracted_media_and_a_changed_image_fails(tmp_path):
    inputs, _, _ = whoops_inputs(tmp_path)
    spec = pin('whoops', {'images': 2}, inputs, tmp_path)
    assert run_conversion(spec, inputs, tmp_path / 'ok')['count'] == 2
    (tmp_path / 'changed').mkdir()
    other, _, _ = whoops_inputs(tmp_path / 'changed', second=png('different'))
    with pytest.raises(ValueError, match='row digest'):
        run_conversion(spec, other, tmp_path / 'bad')
    assert digest_existing(tmp_path / 'ok/records.jsonl', 'jsonl')['rows_sha256'] == spec['rows_sha256']


def test_whoops_refuses_an_archive_missing_a_csv_image_or_with_an_unexpected_population(tmp_path):
    inputs, _, _ = whoops_inputs(tmp_path)
    with pytest.raises(ValueError, match='expected number'):
        CONVERTERS['whoops']({'images': 3}, inputs, tmp_path / 'a', lambda: None)
    broken = tmp_path / 'broken.zip'
    with zipfile.ZipFile(broken, 'w') as z:
        z.writestr('whoops_images/img-a.png', png('first'))
        z.writestr('whoops_images/img-c.png', png('third'))
    with pytest.raises(ValueError, match='absent from the archive'):
        CONVERTERS['whoops']({'images': 2}, {**inputs, 'source_zip': broken}, tmp_path / 'b', lambda: None)


# ---- LLaVA-Bench -----------------------------------------------------------------------------------------------

def llava_inputs(tmp_path):
    (tmp_path / 'q.jsonl').write_text('\n'.join(json.dumps(x) for x in [
        {'question_id': 0, 'image': '001.jpg', 'text': 'What is shown?', 'category': 'conv'},
        {'question_id': 1, 'image': '001.jpg', 'text': 'Describe it.', 'category': 'detail'},
        {'question_id': 2, 'image': '002.jpg', 'text': 'Why?', 'category': 'complex'}]) + '\n')
    (tmp_path / 'c.jsonl').write_text('\n'.join(json.dumps(x) for x in [
        {'id': 'ctx-1', 'image': '001.jpg', 'caption': 'A dog.'}, {'id': 'ctx-2', 'image': '002.jpg', 'caption': 'A cat.'}]) + '\n')
    (tmp_path / '001.jpg').write_bytes(jpg('dog'))
    (tmp_path / '002.jpg').write_bytes(jpg('cat'))
    return {'questions': tmp_path / 'q.jsonl', 'context': tmp_path / 'c.jsonl', 'image_001': tmp_path / '001.jpg', 'image_002': tmp_path / '002.jpg'}


def test_llava_bench_joins_each_question_to_its_image_context_and_copies_the_images_unchanged(tmp_path):
    result = CONVERTERS['llava_bench']({'questions': 3, 'images': 2}, llava_inputs(tmp_path), tmp_path / 'out', lambda: None)
    rows = read_jsonl(result['path'])
    assert [r['question_id'] for r in rows] == [0, 1, 2] and rows[1]['question'] == 'Describe it.' and rows[1]['category'] == 'detail'
    assert rows[0]['context_caption'] == 'A dog.' and rows[0]['context_id'] == 'ctx-1' and rows[2]['context_caption'] == 'A cat.'
    assert rows[0]['media_path'] == 'images/001.jpg' and rows[0]['image_sha256'] == hashlib.sha256(jpg('dog')).hexdigest()
    assert (result['media_dir'] / 'images/002.jpg').read_bytes() == jpg('cat')
    assert sorted(p.name for p in (result['media_dir'] / 'images').iterdir()) == ['001.jpg', '002.jpg']


def test_llava_bench_refuses_a_different_population_and_a_question_without_context(tmp_path):
    inputs = llava_inputs(tmp_path)
    with pytest.raises(ValueError, match='population'):
        CONVERTERS['llava_bench']({}, inputs, tmp_path / 'a', lambda: None)  # the defaults are the real 60 questions and 24 images
    (tmp_path / 'q.jsonl').write_text(json.dumps({'question_id': 9, 'image': '003.jpg', 'text': 'x', 'category': 'conv'}) + '\n')
    with pytest.raises(ValueError, match='no context caption'):
        CONVERTERS['llava_bench']({'questions': 1, 'images': 2}, inputs, tmp_path / 'b', lambda: None)


# ---- MM-Vet ----------------------------------------------------------------------------------------------------

def mm_vet_zip(path, a=None):
    annotations = {'v1_0': {'imagename': 'v1_0.jpg', 'question': 'How many?', 'answer': '3', 'capability': ['rec'], 'imagesource': 'VCR'},
                   'v1_1': {'imagename': 'v1_1.jpg', 'question': 'Which?', 'answer': 'red', 'capability': ['ocr', 'spat'], 'imagesource': 'web'}}
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mm-vet/mm-vet.json', json.dumps(annotations))
        z.writestr('mm-vet/bard_set.json', json.dumps(['v1_1']))
        z.writestr('mm-vet/images/', b'')
        z.writestr('mm-vet/images/v1_0.jpg', a or jpg('zero'))
        z.writestr('mm-vet/images/v1_1.jpg', jpg('one'))
    return path


def test_mm_vet_keeps_annotation_order_flags_the_bard_set_and_extracts_the_exact_images(tmp_path):
    zip_path = mm_vet_zip(tmp_path / 'mm-vet.zip')
    result = CONVERTERS['mm_vet']({'annotations': 2, 'bard_set': 1, 'images': 2}, {'source_zip': zip_path}, tmp_path / 'out', lambda: None)
    rows = read_jsonl(result['path'])
    assert [r['source_id'] for r in rows] == ['v1_0', 'v1_1'] and [r['bard_set'] for r in rows] == [False, True]
    assert rows[1]['capability'] == ['ocr', 'spat'] and rows[0]['answer'] == '3' and rows[0]['imagesource'] == 'VCR'
    assert rows[0]['media_path'] == 'images/v1_0.jpg' and rows[0]['image_sha256'] == hashlib.sha256(jpg('zero')).hexdigest()
    assert (result['media_dir'] / 'images/v1_0.jpg').read_bytes() == jpg('zero')


def test_mm_vet_recipe_fails_when_an_image_or_the_population_differs(tmp_path):
    zip_path = mm_vet_zip(tmp_path / 'mm-vet.zip')
    params = {'annotations': 2, 'bard_set': 1, 'images': 2}
    spec = pin('mm_vet', params, {'source_zip': zip_path}, tmp_path)
    assert run_conversion(spec, {'source_zip': zip_path}, tmp_path / 'ok')['media_dir'] == tmp_path / 'ok/media'
    changed = mm_vet_zip(tmp_path / 'changed.zip', a=jpg('ZERO'))
    with pytest.raises(ValueError):  # the changed image changes image_sha256 in a row, so the row digest differs first
        run_conversion(spec, {'source_zip': changed}, tmp_path / 'bad')
    with pytest.raises(ValueError, match='population'):
        CONVERTERS['mm_vet']({}, {'source_zip': zip_path}, tmp_path / 'wrong', lambda: None)  # defaults are the real 218/168/200


def test_a_recipe_that_pins_media_refuses_a_converter_that_extracted_none_or_different_media(tmp_path):
    zip_path = mm_vet_zip(tmp_path / 'mm-vet.zip')
    params = {'annotations': 2, 'bard_set': 1, 'images': 2}
    spec = pin('mm_vet', params, {'source_zip': zip_path}, tmp_path)
    assert len(spec['media_sha256']) == 64
    with pytest.raises(ValueError, match='Extracted media differ'):
        run_conversion({**spec, 'media_sha256': '0' * 64}, {'source_zip': zip_path}, tmp_path / 'out')


# ---- IllusionVQA (embedded image bytes) ------------------------------------------------------------------------

def illusion_parquet(path, rows):
    import pyarrow as pa
    import pyarrow.parquet as pq
    image = pa.struct([pa.field('bytes', pa.binary()), pa.field('path', pa.string())])
    schema = pa.schema([('id', pa.int64()), ('question', pa.string()), ('options', pa.list_(pa.string())), ('answer', pa.string()),
                        ('category', pa.string()), ('source', pa.string()), ('url', pa.string()), ('reasoning', pa.string()), ('image', image)])
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    return path


def illusion_row(i, data, **extra):
    return {'id': i, 'question': f'Q{i}', 'options': ['a', 'b'], 'answer': 'a', 'category': 'cat', 'source': None, 'url': None,
            'reasoning': None, 'image': {'bytes': data, 'path': f'{i}.png'}, **extra}


def illusion_inputs(tmp_path, first=None):
    return {'comprehension': illusion_parquet(tmp_path / 'c.parquet', [illusion_row(1, first or png('a')), illusion_row(2, jpg('b'))]),
            'soft_localization': illusion_parquet(tmp_path / 's.parquet', [illusion_row(1, png('c'), reasoning='because')])}


def test_illusionvqa_stacks_both_tasks_adds_identity_and_embeds_each_image_unchanged(tmp_path):
    import pyarrow.parquet as pq
    counts = {'comprehension': 2, 'soft-localization': 1}
    result = CONVERTERS['illusionvqa']({'counts': counts}, illusion_inputs(tmp_path), tmp_path / 'out', lambda: None)
    rows = pq.read_table(result['path']).to_pylist()
    assert result['count'] == 3 and [r['source_id'] for r in rows] == ['comprehension:test:1', 'comprehension:test:2', 'soft-localization:test:1']
    assert rows[0]['task'] == 'comprehension' and rows[0]['split'] == 'test' and rows[0]['source_file'] == 'data/test-00000-of-00001.parquet'
    assert rows[0]['images'] == [{'bytes': png('a'), 'path': '1.png'}] and rows[1]['images'][0]['bytes'] == jpg('b')
    assert rows[2]['reasoning'] == 'because' and rows[0]['reasoning'] is None and rows[0]['options'] == ['a', 'b']


def test_rows_carrying_image_bytes_are_digested_with_the_bytes_hashed_in_place(tmp_path):
    counts = {'comprehension': 2, 'soft-localization': 1}
    inputs = illusion_inputs(tmp_path)
    result = CONVERTERS['illusionvqa']({'counts': counts}, inputs, tmp_path / 'out', lambda: None)
    assert media.digest_existing_with_bytes(result['path']) == {'count': 3, 'rows_sha256': result['rows_sha256']}
    with pytest.raises(TypeError):  # the ordinary digest cannot hash bytes, which is why this one exists
        digest_existing(result['path'], 'parquet')
    spec = {'name': 'illusionvqa', 'params': {'counts': counts}, 'count': 3, 'rows_sha256': result['rows_sha256']}
    assert run_conversion(spec, inputs, tmp_path / 'again')['rows_sha256'] == result['rows_sha256']
    (tmp_path / 'x').mkdir()
    changed = illusion_inputs(tmp_path / 'x', first=png('A'))
    with pytest.raises(ValueError, match='row digest'):
        run_conversion(spec, changed, tmp_path / 'bad')


def test_illusionvqa_refuses_a_wrong_task_population_and_a_row_without_an_image(tmp_path):
    with pytest.raises(ValueError, match='expected 435'):
        CONVERTERS['illusionvqa']({}, illusion_inputs(tmp_path), tmp_path / 'out', lambda: None)
    inputs = {'comprehension': illusion_parquet(tmp_path / 'n.parquet', [illusion_row(1, png('a'))]),
              'soft_localization': illusion_parquet(tmp_path / 'm.parquet', [{**illusion_row(1, b''), 'image': None}])}
    with pytest.raises(ValueError, match='no embedded image'):
        CONVERTERS['illusionvqa']({'counts': {'comprehension': 1, 'soft-localization': 1}}, inputs, tmp_path / 'o2', lambda: None)


# ---- JailBreakV-28K ---------------------------------------------------------------------------------------------

def test_jailbreakv_exposes_media_only_for_images_in_the_released_tree_and_keeps_every_row(tmp_path):
    source = tmp_path / 'jb.csv'
    source.write_bytes(b'\xef\xbb\xbf' + 'id,jailbreak_query,image_path,format\n1,Query one,figstep/a.png,Template\n2,"Query, two",llm_transfer_attack/gone.png,Persuade\n3,Query three,,Logic\n'.encode())
    params = {'released_images': ['figstep/a.png', 'figstep/other.png']}
    result = CONVERTERS['jailbreakv_28k'](params, {'source_csv': source}, tmp_path / 'out', lambda: None)
    rows = read_jsonl(result['path'])
    assert result['count'] == 3 and [r['id'] for r in rows] == ['1', '2', '3']
    assert [r['media_path'] for r in rows] == ['figstep/a.png', '', '']
    assert rows[1]['jailbreak_query'] == 'Query, two' and rows[1]['image_path'] == 'llm_transfer_attack/gone.png'  # the original reference is kept
    assert 'media_dir' not in result  # media are served by the catalogue's pinned URL, not extracted


def test_jailbreakv_refuses_a_row_without_an_official_id(tmp_path):
    source = tmp_path / 'jb.csv'
    source.write_text('id,image_path\n,figstep/a.png\n')
    with pytest.raises(ValueError, match='official ID'):
        CONVERTERS['jailbreakv_28k']({'released_images': []}, {'source_csv': source}, tmp_path / 'out', lambda: None)


# ---- OmniSafeBench-MM ------------------------------------------------------------------------------------------

def test_omnisafebench_strips_the_dataset_prefix_to_the_hubs_images_path_and_keeps_the_original_reference(tmp_path):
    source = tmp_path / 'data_full.json'
    source.write_text(json.dumps([{'id': 0, 'original_prompt': 'p0', 'image_path': 'dataset/images/0.png', 'style': 'declarative'},
                                   {'id': 1, 'original_prompt': 'p1', 'image_path': 'dataset/images/1.png', 'style': 'instructive'}]))
    result = CONVERTERS['omnisafebench_mm']({}, {'source_json': source}, tmp_path / 'out', lambda: None)
    rows = read_jsonl(result['path'])
    assert [r['media_path'] for r in rows] == ['images/0.png', 'images/1.png'] and rows[0]['image_path'] == 'dataset/images/0.png'
    assert rows[1]['style'] == 'instructive' and result['count'] == 2


def test_omnisafebench_refuses_an_unexpected_or_escaping_media_reference(tmp_path):
    for reference in ('images/0.png', 'dataset/images/../../etc/passwd', 'other/0.png'):
        source = tmp_path / 'data_full.json'
        source.write_text(json.dumps([{'id': 0, 'image_path': reference}]))
        with pytest.raises(ValueError, match='Unexpected OmniSafeBench media reference'):
            CONVERTERS['omnisafebench_mm']({}, {'source_json': source}, tmp_path / 'out', lambda: None)


# ---- HC-Bench ------------------------------------------------------------------------------------------------

def test_hc_bench_builds_the_index_csv_from_the_pinned_images_and_copies_them_unchanged(tmp_path):
    inputs = {}
    for key, tag in (('image_02', 'two'), ('image_01', 'one')):  # key order, not argument order, sets row order
        (tmp_path / f'{key}.png').write_bytes(png(tag))
        inputs[key] = tmp_path / f'{key}.png'
    result = CONVERTERS['hc_bench']({}, inputs, tmp_path / 'out', lambda: None)
    one = png('one')
    text = Path(result['path']).read_bytes().decode()
    assert text.splitlines()[0] == 'path,source_subset,source_bytes,source_sha256' and '\r\n' in text  # csv-module dialect, as the maintainer's file
    assert text.splitlines()[1] == f'wild/image_01.png,wild,{len(one)},{hashlib.sha256(one).hexdigest()}'
    assert result['format'] == 'csv' and result['count'] == 2 and result['file_sha256'] == hashlib.sha256(text.encode()).hexdigest()
    assert (result['media_dir'] / 'wild/image_02.png').read_bytes() == png('two')
    # the row digest is over the CSV's string cells, so the maintainer's CSV can be digested the same way
    from dataset_atlas.converters import RowDigest
    digest = RowDigest()
    for row in csv.DictReader(io.StringIO(text, newline='')):
        digest.add(row)
    assert digest.hexdigest() == result['rows_sha256']


def test_hc_bench_recipe_pins_media_and_refuses_non_png_or_empty_input(tmp_path):
    (tmp_path / 'image_01.png').write_bytes(png('one'))
    inputs = {'image_01': tmp_path / 'image_01.png'}
    spec = pin('hc_bench', {}, inputs, tmp_path)
    assert run_conversion(spec, inputs, tmp_path / 'ok')['count'] == 1
    (tmp_path / 'image_01.png').write_bytes(jpg('now a jpeg'))
    with pytest.raises(ValueError, match='not a png'):
        CONVERTERS['hc_bench']({}, inputs, tmp_path / 'bad', lambda: None)
    with pytest.raises(ValueError, match='no images'):
        CONVERTERS['hc_bench']({}, {}, tmp_path / 'empty', lambda: None)


# ---- MMBench -------------------------------------------------------------------------------------------------

def real_image(fmt, color):
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', (3, 2), color).save(buffer, format=fmt)
    return buffer.getvalue()


def mmbench_tsv(path, png_data=None):
    import base64
    header = ['index', 'question', 'hint', 'A', 'B', 'C', 'D', 'answer', 'category', 'image', 'source', 'l2-category', 'comment', 'split']
    rows = [['1', 'Which?', 'a hint', 'cat', 'dog', '', '', 'A', 'obj', base64.b64encode(png_data or real_image('PNG', 'red')).decode(), 'src', 'l2', '', 'dev'],
            ['1000001', 'Which?', 'a hint', 'dog', 'cat', '', '', 'B', 'obj', '1', 'src', 'l2', '', 'dev'],  # a circular variant points at row 1's image
            ['2', 'Where?', '', 'in', 'out', 'up', 'down', 'C', 'loc', base64.b64encode(real_image('JPEG', 'blue')).decode(), 'src', 'l2', '', 'dev']]
    path.write_text('\n'.join('\t'.join(r) for r in [header] + rows) + '\n')
    return {'source_tsv': path}


def test_mmbench_decodes_each_image_once_follows_variant_references_and_formats_choices(tmp_path):
    import pyarrow.parquet as pq
    result = CONVERTERS['mmbench_dev']({'image_groups': 2}, mmbench_tsv(tmp_path / 'm.tsv'), tmp_path / 'out', lambda: None)
    rows = pq.read_table(result['path']).to_pylist()
    assert result['count'] == 3 and [r['source_id'] for r in rows] == ['1', '1000001', '2']
    assert rows[0]['choices'] == ['A. cat', 'B. dog'] and rows[2]['choices'] == ['A. in', 'B. out', 'C. up', 'D. down']  # empty options are dropped
    assert rows[1]['source_image_index'] == '1' and rows[1]['image'] == rows[0]['image'] and rows[2]['image'].endswith('.jpg')
    assert rows[0]['image'] == rows[0]['image_sha256'] + '.png' and (rows[0]['image_width'], rows[0]['image_height']) == (3, 2)
    assert rows[0]['hint'] == 'a hint' and rows[0]['A'] == 'cat' and rows[0]['answer'] == 'A'  # original columns are kept
    assert sorted(p.name for p in result['media_dir'].iterdir()) == sorted({r['image'] for r in rows})  # flat, one file per distinct image
    assert (result['media_dir'] / rows[0]['image']).read_bytes() == real_image('PNG', 'red')
    assert digest_existing(result['path'], 'parquet')['rows_sha256'] == result['rows_sha256']


def test_mmbench_recipe_pins_rows_and_media_and_refuses_a_different_image_population(tmp_path):
    inputs = mmbench_tsv(tmp_path / 'm.tsv')
    spec = pin('mmbench_dev', {'image_groups': 2}, inputs, tmp_path)
    assert run_conversion(spec, inputs, tmp_path / 'ok')['count'] == 3
    with pytest.raises(ValueError, match='image-group population'):
        CONVERTERS['mmbench_dev']({'image_groups': 3}, inputs, tmp_path / 'bad', lambda: None)
    (tmp_path / 'other').mkdir()
    other = mmbench_tsv(tmp_path / 'other/m.tsv', png_data=real_image('PNG', 'green'))
    with pytest.raises(ValueError, match='row digest'):
        run_conversion(spec, other, tmp_path / 'changed')


def test_mmbench_refuses_cyclic_missing_and_unsupported_image_references(tmp_path):
    with pytest.raises(ValueError, match='Cyclic'):
        media.mmbench_image('1', {'1': '2', '2': '1'})
    with pytest.raises(ValueError, match='Missing'):
        media.mmbench_image('1', {'1': '9'})
    import base64
    bad = tmp_path / 'bad.tsv'
    bad.write_text('index\tA\tB\tC\tD\timage\n1\ta\tb\t\t\t' + base64.b64encode(b'GIF89a' + b'x' * 80).decode() + '\n')
    with pytest.raises(Exception):  # Pillow cannot identify or the format is not JPEG/PNG
        CONVERTERS['mmbench_dev']({}, {'source_tsv': bad}, tmp_path / 'out', lambda: None)
