"""RSVQA-LR converter on small synthetic split files and archive: each test documents one rule of the maintained table."""
import json
import zipfile
from pathlib import Path

import pytest

from dataset_atlas.converters import CONVERTERS, media_digest, run_conversion

TIFF = b'II*\x00'


def tiff(tag: str) -> bytes:
    return TIFF + tag.encode()


def image(image_id, question_ids):
    return {'id': image_id, 'date_added': 1.5, 'original_name': f'S2_{image_id}.tif', 'sensor': 'S2', 'upperleft_map_x': 10.5,
            'upperleft_map_y': 20.5, 'res_x': '10m', 'res_y': '10m', 'people_id': 0, 'type': 'RGB', 'questions_ids': question_ids, 'active': True}


def question(question_id, image_id, text='Is it a rural or an urban area', kind='rural_urban', answers=None):
    return {'id': question_id, 'date_added': 2.5, 'img_id': image_id, 'people_id': 3, 'type': kind, 'question': text,
            'answers_ids': [question_id] if answers is None else answers, 'active': True}


def answer(answer_id, question_id, text='rural'):
    return {'id': answer_id, 'date_added': 3.5, 'question_id': question_id, 'people_id': 4, 'answer': text, 'active': True}


def stub(identifier):
    return {'id': identifier, 'active': False}


def build(tmp_path: Path, **overrides):
    """Four images (ids 0-3) and four questions (ids 0-3): train owns 0-1, val owns 2, test owns 3. Inactive stubs fill the other ids."""
    layout = {'train': ([0, 1], [0, 1]), 'val': ([2], [2]), 'test': ([3], [3])}
    inputs = {}
    for split, (images, questions) in layout.items():
        tables = {
            'images': {'images': [image(i, [i]) if i in images else stub(i) for i in range(4)]},
            'questions': {'questions': [question(q, q) if q in questions else stub(q) for q in range(4)]},
            'answers': {'answers': [answer(q, q, f'a{q}') if q in questions else stub(q) for q in range(4)]}}
        tables.update(overrides.get(split, {}))
        for kind, table in tables.items():
            path = tmp_path / f'LR_split_{split}_{kind}.json'
            path.write_text(json.dumps(table))
            inputs[f'{split}_{kind}'] = path
    archive = tmp_path / 'Images_LR.zip'
    with zipfile.ZipFile(archive, 'w') as handle:
        handle.writestr('Images_LR/', b'')
        for i in range(4):
            handle.writestr(f'Images_LR/{i}.tif', tiff(str(i)))
    inputs['images_zip'] = archive
    return inputs


def convert(inputs, tmp_path, **params):
    from dataset_atlas.converters import remote_sensing  # noqa: F401
    return CONVERTERS['rsvqa_lr']({'images': 4, **params}, inputs, tmp_path / 'out', lambda: None)


def test_only_active_questions_become_rows_joined_to_their_answer_and_image(tmp_path):
    result = convert(build(tmp_path), tmp_path)
    rows = [json.loads(line) for line in Path(result['path']).read_text().splitlines()]
    assert result['count'] == 4
    assert [(r['split'], r['question_id'], r['answer']) for r in rows] == [('train', 0, 'a0'), ('train', 1, 'a1'), ('val', 2, 'a2'), ('test', 3, 'a3')]
    first = rows[0]
    assert first['image_id'] == 0 and first['image_original_name'] == 'S2_0.tif' and first['image_upperleft_map_x'] == 10.5
    assert first['question_annotator_id'] == 3 and first['answer_annotator_id'] == 4 and first['media_path'] == 'images/0.tif'


def test_images_are_the_archives_exact_bytes_and_the_digest_pins_them(tmp_path):
    result = convert(build(tmp_path), tmp_path)
    stored = Path(result['media_dir']) / 'images' / '2.tif'
    assert stored.read_bytes() == tiff('2')
    rows = [json.loads(line) for line in Path(result['path']).read_text().splitlines()]
    import hashlib
    assert rows[2]['image_sha256'] == hashlib.sha256(tiff('2')).hexdigest()
    spec = {'name': 'rsvqa_lr', 'params': {'images': 4}, 'count': 4, 'rows_sha256': result['rows_sha256'], 'media_sha256': media_digest(result['media_dir'])}
    second = tmp_path / 'second-inputs'
    second.mkdir()
    again = run_conversion(spec, build(second), tmp_path / 'second')
    assert again['rows_sha256'] == result['rows_sha256']


def test_two_questions_may_share_an_image_without_duplicating_it(tmp_path):
    questions = {'questions': [question(0, 0, 'q-a'), question(1, 0, 'q-b', 'count'), stub(2), stub(3)]}
    answers = {'answers': [answer(0, 0, 'yes'), answer(1, 1, '3'), stub(2), stub(3)]}
    images = {'images': [image(0, [0, 1]), stub(1), stub(2), stub(3)]}
    inputs = build(tmp_path, train={'questions': questions, 'answers': answers, 'images': images},
                   val={'questions': {'questions': [stub(i) for i in range(4)]}, 'answers': {'answers': [stub(i) for i in range(4)]},
                        'images': {'images': [stub(i) for i in range(4)]}},
                   test={'questions': {'questions': [stub(i) for i in range(4)]}, 'answers': {'answers': [stub(i) for i in range(4)]},
                         'images': {'images': [stub(i) for i in range(4)]}})
    with pytest.raises(ValueError, match='activate'):
        convert(inputs, tmp_path)  # only one image is active: the release must account for every image
    with zipfile.ZipFile(inputs['images_zip'], 'w') as handle:
        handle.writestr('Images_LR/0.tif', tiff('0'))
    result = convert(inputs, tmp_path, images=1)
    rows = [json.loads(line) for line in Path(result['path']).read_text().splitlines()]
    assert [r['image_id'] for r in rows] == [0, 0] and rows[0]['media_path'] == rows[1]['media_path']
    assert len(list((Path(result['media_dir']) / 'images').iterdir())) == 1


def test_a_question_without_exactly_one_answer_stops_the_conversion(tmp_path):
    inputs = build(tmp_path, train={'questions': {'questions': [question(0, 0, answers=[]), question(1, 1), stub(2), stub(3)]}})
    with pytest.raises(ValueError, match='exactly one active answer'):
        convert(inputs, tmp_path)


def test_an_identifier_active_in_two_splits_is_refused(tmp_path):
    clash = {'questions': [stub(0), stub(1), question(2, 2), stub(3)]}
    inputs = build(tmp_path, train={'questions': clash})
    with pytest.raises(ValueError, match='active in both'):
        convert(inputs, tmp_path)


def test_an_image_missing_from_the_archive_or_not_a_tiff_is_refused(tmp_path):
    inputs = build(tmp_path)
    with zipfile.ZipFile(inputs['images_zip'], 'w') as handle:
        for i in range(3):
            handle.writestr(f'Images_LR/{i}.tif', tiff(str(i)))
    with pytest.raises(ValueError, match='expected number'):
        convert(inputs, tmp_path)
    with zipfile.ZipFile(inputs['images_zip'], 'w') as handle:
        for i in range(4):
            handle.writestr(f'Images_LR/{i}.tif', b'GIF89a' if i == 1 else tiff(str(i)))
    with pytest.raises(ValueError, match='not a TIFF'):
        convert(inputs, tmp_path)


def test_zip_image_bound_is_checked_before_member_decompression(tmp_path,monkeypatch):
    inputs=build(tmp_path)
    real_infos=zipfile.ZipFile.infolist
    def oversized_infos(archive):
        infos=real_infos(archive)
        for info in infos:
            if info.filename.endswith('0.tif'):info.file_size=10_000_001
        return infos
    def unexpected_read(*args,**kwargs):raise AssertionError('Oversized TIFF must refuse before decompression')
    monkeypatch.setattr(zipfile.ZipFile,'infolist',oversized_infos)
    monkeypatch.setattr(zipfile.ZipFile,'open',unexpected_read)
    with pytest.raises(ValueError,match='before decompression'):convert(inputs,tmp_path)
