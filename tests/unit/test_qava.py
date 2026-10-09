import hashlib
import io
import json
import tarfile

import pytest
from PIL import Image


def _fixture(tmp_path, dataset, *, broken=False):
    prefix = 'qava-test/annotation/'
    groups = []; questions = []; answers = []
    for image_id in range(1, 33):
        items = []
        for index in range(50):
            qid = image_id * 1000 + index
            question = f'Question {qid}?'
            items.append({'question_id': qid, 'question': question})
            questions.append({'question_id': qid, 'image_id': image_id, 'question': question})
            answers.append({'question_id': qid, 'image_id': image_id, 'multiple_choice_answer': 'yes'})
        groups.append({'image': f'val2014/COCO_val2014_{image_id:012d}.jpg', 'ques': items})
    if broken:
        answers[0]['image_id'] = 999
    files = {'vqa_val_image_32_ques_50.json': groups,
             'eval_questions_image_32_ques_50.json': {'data_subtype': 'val2014', 'questions': questions},
             'eval_annotations_image_32_ques_50.json': {'data_subtype': 'val2014', 'annotations': answers}}
    path = tmp_path / 'qava.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        for name, value in files.items():
            payload = json.dumps(value).encode()
            info = tarfile.TarInfo(prefix + name); info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    dataset.id = 'qava-fixture'; dataset.release = 'fixture-release'; dataset.snapshot_id = 'fixture-snapshot'
    dataset.adapter = 'qava'
    dataset.adapter_config = {'archive': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                              'archive_prefix': 'qava-test'}
    return path


def test_qava_native_join_and_bounded_original_media(tmp_path, pack, monkeypatch):
    from dataset_atlas.adapters.qava import QavaAdapter
    _fixture(tmp_path, pack.dataset)
    adapter = QavaAdapter(pack.dataset)
    source = adapter.prepare(adapter.plan(100, 5_000_000))
    assert adapter.count == 1600
    rows = adapter.iter_records(source, limit=100).records
    assert len(rows) == 100
    assert len({r.assets[0].id for r in adapter._records()}) == 32
    assert rows[0].question == 'Question 1000?'
    image = io.BytesIO(); Image.new('RGB', (8, 6), 'red').save(image, 'JPEG')
    payload = image.getvalue(); md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    class Response:
        status_code = 200
        headers = {'Content-Length': str(len(payload)), 'ETag': f'"{md5}"'}
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def raise_for_status(self): pass
        def iter_bytes(self, _): yield payload
    monkeypatch.setattr('dataset_atlas.adapters.qava.httpx.stream', lambda *_, **__: Response())
    handle = adapter.resolve_asset(source, rows[0].assets[0].uri)
    assert handle.data == payload and handle.media_type == 'image/jpeg'


def test_qava_rejects_disagreeing_answer_image(tmp_path, pack):
    from dataset_atlas.adapters.qava import QavaAdapter
    _fixture(tmp_path, pack.dataset, broken=True)
    with pytest.raises(ValueError, match='disagree'):
        QavaAdapter(pack.dataset).count
