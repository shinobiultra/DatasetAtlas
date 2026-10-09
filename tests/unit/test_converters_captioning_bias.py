"""COCO-GB converter on small synthetic archives: variant scoping, secret test flags and the fine-tune subset caveat."""
import json
import zipfile
from pathlib import Path

import pytest

from dataset_atlas.converters import CONVERTERS
from dataset_atlas.converters import captioning_bias  # noqa: F401  (registers the converter)


def image(cocoid, folder='val2014', split='test', gender=1, category='1 2', sentids=(1, 2), present=None, with_labels=True):
    present = list(sentids if present is None else present)
    record = {'filepath': folder, 'filename': f'COCO_{folder}_{cocoid:012d}.jpg', 'imgid': cocoid % 100, 'split': split, 'cocoid': cocoid,
              'sentids': list(sentids), 'sentences': [{'tokens': ['a'], 'raw': f'Caption {s}. ', 'imgid': 0, 'sentid': s} for s in present]}
    if with_labels:
        record.update(gender=gender, category_id=category)
    return record


def build(tmp_path, v1_images, secret, v2=None):
    v1 = tmp_path / 'v1.zip'
    with zipfile.ZipFile(v1, 'w') as z:
        z.writestr('Ksplit_gender_category.json', json.dumps({'images': v1_images, 'dataset': 'coco', 'categories': [{'id': 1}, {'id': 2}], 'secret_test': secret}))
    v2zip = tmp_path / 'v2.zip'
    with zipfile.ZipFile(v2zip, 'w') as z:
        for name, images in (v2 or {'COCOv2_train.json': [], 'COCOv2_test.json': [], 'COCOv2_fine_tune.json': []}).items():
            z.writestr(name, json.dumps({'images': images}))
    return {'v1_zip': v1, 'v2_zip': v2zip}


def run(inputs, tmp_path):
    result = CONVERTERS['coco_gb']({}, inputs, tmp_path / 'out', lambda: None)
    return result, [json.loads(line) for line in Path(result['path']).read_text().splitlines()]


def test_variants_scope_identity_and_the_secret_test_flags_only_its_images(tmp_path):
    v1 = [image(10), image(11, gender=2), image(12, folder='train2014', split='train', gender=0)]
    secret = [{'coco_id': 10, 'gender': 1, 'category_id': '1 2'}]
    v2 = {'COCOv2_train.json': [image(10, split='train')], 'COCOv2_test.json': [image(12, folder='train2014')], 'COCOv2_fine_tune.json': [image(10, with_labels=False)]}
    result, rows = run(build(tmp_path, v1, secret, v2), tmp_path)
    assert result['count'] == 6
    ids = [r['source_id'] for r in rows]
    assert len(set(ids)) == 6 and 'v1:test:10' in ids and 'v2:fine_tune:10' in ids and 'v2:train:10' in ids
    assert [r['secret_test'] for r in rows if r['release_variant'] == 'v1'] == [True, False, False]
    assert all(r['secret_test'] is None for r in rows if r['release_variant'] == 'v2')
    fine = next(r for r in rows if r['partition'] == 'fine_tune')
    assert fine['gender'] is None and fine['category_id'] is None and fine['category_ids'] is None
    assert rows[0]['coco_url'] == 'https://images.cocodataset.org/val2014/COCO_val2014_000000000010.jpg' and rows[0]['category_ids'] == [1, 2]
    assert rows[0]['captions']==[sentence['raw'] for sentence in v1[0]['sentences']]
    assert rows[0]['native_sentences']==v1[0]['sentences'] and rows[0]['captions'][0].endswith(' ')


def test_a_fine_tune_record_that_keeps_only_some_sentences_is_flagged_not_rejected(tmp_path):
    v2 = {'COCOv2_train.json': [], 'COCOv2_test.json': [], 'COCOv2_fine_tune.json': [image(5, folder='train2014', sentids=(1, 2, 3), present=(1, 3), with_labels=False)]}
    _, rows = run(build(tmp_path, [image(1)], [], v2), tmp_path)
    row = rows[-1]
    assert row['captions_subset_of_listed'] is True and row['caption_ids'] == [1, 3] and row['listed_sentence_ids'] == [1, 2, 3]


def test_sentences_outside_their_id_list_and_mismatched_files_are_refused(tmp_path):
    bad = image(7, sentids=(1, 2), present=(1, 9))
    with pytest.raises(ValueError, match='does not contain'):
        run(build(tmp_path, [bad], []), tmp_path)
    sub = tmp_path / 'b'
    sub.mkdir()
    wrong = image(8)
    wrong['filename'] = 'COCO_val2014_000000000999.jpg'
    with pytest.raises(ValueError, match='does not match its COCO ID'):
        run(build(sub, [wrong], []), sub)


def test_a_secret_test_that_disagrees_with_the_split_is_refused(tmp_path):
    with pytest.raises(ValueError, match='disagrees'):
        run(build(tmp_path, [image(10)], [{'coco_id': 10, 'gender': 0, 'category_id': '1 2'}]), tmp_path)
    sub = tmp_path / 'c'
    sub.mkdir()
    with pytest.raises(ValueError, match='secret_test must list'):
        run(build(sub, [image(10)], [{'coco_id': 99, 'gender': 1, 'category_id': '1'}]), sub)


@pytest.mark.parametrize('limit',['max_annotation_member_bytes','max_annotation_expanded_bytes'])
def test_annotation_expansion_is_refused_before_reading_member(tmp_path,monkeypatch,limit):
    inputs=build(tmp_path,[image(1)],[])
    def unexpected_read(*args,**kwargs):raise AssertionError('Oversized annotation must fail before decompression')
    monkeypatch.setattr(zipfile.ZipFile,'open',unexpected_read)
    with pytest.raises(ValueError,match='expanded byte budget'):
        CONVERTERS['coco_gb']({limit:10},inputs,tmp_path/'out',lambda:None)
