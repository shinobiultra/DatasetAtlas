import hashlib
import json
import zipfile

import pytest

from dataset_atlas.adapters.mm_safetybench import MMSafetyBenchAdapter
from dataset_atlas.models import Dataset


def fixture(tmp_path, missing=False):
    annotation = tmp_path / 'questions.json'
    annotation.write_text(json.dumps({'0': {'Question': 'Fixture question', 'Rephrased Question': 'Text-image fixture',
                                          'Rephrased Question(SD)': 'Image fixture'}}))
    images = tmp_path / 'images.zip'
    with zipfile.ZipFile(images, 'w') as z:
        for key in ['0', '2']:
            for variant in ['SD', 'SD_TYPO', 'TYPO']:
                if not (missing and variant == 'TYPO'):
                    z.writestr(f'MM-SafetyBench(imgs)/scenario/{variant}/{key}.jpg', b'fixture')
    return MMSafetyBenchAdapter(Dataset(id='mmsafety', name='Fixture', adapter='mm_safetybench', adapter_config={
        'annotations': [{'path_key': 'questions_path', 'scenario': 'scenario', 'source_name': 'questions.json'}],
        'questions_path': str(annotation), 'images_path': str(images), 'mapping': {'question': 'Question'},
        'source_files': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [annotation, images]],
        'local_archives': {'images': {'path_key': 'images_path'}}}))


def test_question_variants_and_source_only_images_are_distinct(tmp_path):
    adapter = fixture(tmp_path)
    rows = adapter.iter_records(adapter.prepare(adapter.plan(10, 100000))).records
    assert len(rows) == 2
    assert rows[0].question == 'Fixture question'
    assert [a.metadata['condition'] for a in rows[0].assets] == ['SD', 'SD_TYPO', 'TYPO']
    assert [a.metadata['question'] for a in rows[0].assets] == ['Image fixture', 'Text-image fixture', 'Text-image fixture']
    assert rows[1].question is None and rows[1].source['annotation_status'] == 'not_released'
    assert len(rows[1].assets) == 3
    assert adapter.validate_media(100000)['referenced_images'] == 6


def test_incomplete_image_variant_group_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='incomplete image variants'):
        fixture(tmp_path, missing=True)._rows()
