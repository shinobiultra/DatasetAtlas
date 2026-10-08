"""RSVQA-LR: the author's Zenodo split files joined into one question per row, with the original TIFF images extracted unchanged.

Each split file (`LR_split_<split>_{images,questions,answers}.json`) lists *every* identifier of the release and marks only the
members of that split `active`; the others are bare `{id, active: false}` stubs. A row is therefore one *active* question with its
single active answer and its active image. Nothing is invented: a question without exactly one answer, an image outside the
archive, or an identifier claimed by two splits stops the conversion.
"""
from __future__ import annotations
import hashlib
import json
import zipfile
from pathlib import Path
from . import converter, write_rows
from .media import checked_image, store_image, MAX_IMAGE_BYTES

SPLITS = ('train', 'val', 'test')
TIFF_MAGIC = (b'II*\x00', b'MM\x00*')
IMAGE_PREFIX = 'Images_LR/'


def _active(table: dict, key: str, split: str) -> dict[int, dict]:
    items = table.get(key)
    if not isinstance(items, list):
        raise ValueError(f'RSVQA-LR {split} {key} file lacks its {key!r} list')
    active: dict[int, dict] = {}
    for item in items:
        if item.get('active') is True:
            if item['id'] in active:
                raise ValueError(f'RSVQA-LR {split} {key} repeats identifier {item["id"]}')
            active[item['id']] = item
    return active


@converter('rsvqa_lr')
def rsvqa_lr(params, inputs, output_dir, check):
    """One row per active question: question, answer, question type, annotator and the image's native sensor/geolocation fields.

    Adds `split`, `media_path` (images/<image id>.tif) and `image_sha256`. The image bytes are the archive's own, never re-encoded."""
    media_dir = Path(output_dir) / 'media'
    expected = params.get('images', 772)
    loaded = {}
    for split in SPLITS:
        loaded[split] = tuple(
            _active(json.loads(Path(inputs[f'{split}_{kind}']).read_text()), kind, split) for kind in ('images', 'questions', 'answers'))
    seen_images: dict[int, str] = {}
    seen_questions: dict[int, str] = {}
    for split in SPLITS:
        images, questions, answers = loaded[split]
        for image_id in images:
            if image_id in seen_images:
                raise ValueError(f'RSVQA-LR image {image_id} is active in both {seen_images[image_id]} and {split}')
            seen_images[image_id] = split
        for question_id in questions:
            if question_id in seen_questions:
                raise ValueError(f'RSVQA-LR question {question_id} is active in both {seen_questions[question_id]} and {split}')
            seen_questions[question_id] = split
    if len(seen_images) != expected:
        raise ValueError(f'RSVQA-LR splits activate {len(seen_images)} images; the release has {expected}')

    def rows():
        with zipfile.ZipFile(inputs['images_zip']) as archive:
            files = {info.filename: info for info in archive.infolist()
                     if not info.is_dir() and info.filename.startswith(IMAGE_PREFIX) and info.filename.endswith('.tif')}
            if len(files) != expected:
                raise ValueError('RSVQA-LR archive does not contain the expected number of TIFF images')
            stored: dict[int, tuple[str, str]] = {}
            for split in SPLITS:
                images, questions, answers = loaded[split]
                for question_id in sorted(questions):
                    check()
                    question = questions[question_id]
                    image = images.get(question['img_id'])
                    if image is None:
                        raise ValueError(f'RSVQA-LR question {question_id} names image {question["img_id"]}, which is not active in {split}')
                    answer_ids = question['answers_ids']
                    if len(answer_ids) != 1 or answer_ids[0] not in answers or answers[answer_ids[0]]['question_id'] != question_id:
                        raise ValueError(f'RSVQA-LR question {question_id} does not have exactly one active answer of its own')
                    answer = answers[answer_ids[0]]
                    image_id = image['id']
                    if image_id not in stored:
                        name = f'{IMAGE_PREFIX}{image_id}.tif'
                        if name not in files:
                            raise ValueError(f'RSVQA-LR image absent from the archive: {name}')
                        info=files[name]
                        if not 1<=info.file_size<=MAX_IMAGE_BYTES:raise ValueError('RSVQA-LR native TIFF exceeds image byte budget before decompression')
                        with archive.open(info) as stream:data=checked_image(stream.read(MAX_IMAGE_BYTES+1))
                        if len(data)!=info.file_size:raise ValueError('RSVQA-LR native TIFF length changed')
                        if not data.startswith(TIFF_MAGIC):
                            raise ValueError(f'RSVQA-LR image {image_id} is not a TIFF')
                        relative = f'images/{image_id}.tif'
                        store_image(media_dir, relative, data)
                        stored[image_id] = (relative, hashlib.sha256(data).hexdigest())
                    relative, digest = stored[image_id]
                    yield {
                        'question_id': question_id, 'split': split, 'image_id': image_id,
                        'question': question['question'], 'question_type': question['type'], 'answer': answer['answer'],
                        'answer_id': answer['id'], 'question_annotator_id': question['people_id'],
                        'answer_annotator_id': answer['people_id'], 'question_date_added': question['date_added'],
                        'answer_date_added': answer['date_added'], 'image_original_name': image['original_name'],
                        'image_sensor': image['sensor'], 'image_type': image['type'],
                        'image_upperleft_map_x': image['upperleft_map_x'], 'image_upperleft_map_y': image['upperleft_map_y'],
                        'image_res_x': image['res_x'], 'image_res_y': image['res_y'],
                        'media_path': relative, 'image_sha256': digest}
            unused = set(seen_images) - set(stored)
            if unused:
                raise ValueError(f'RSVQA-LR images without any active question: {sorted(unused)[:5]}')
    result = write_rows(rows, Path(output_dir) / 'records.jsonl', 'jsonl', check)
    return {**result, 'media_dir': media_dir}
