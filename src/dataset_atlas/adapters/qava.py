"""Pinned QAVA 32-image/50-question VQA v2 subset and official COCO media."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

import httpx
from PIL import Image

from dataset_atlas.models import Asset, Record, stable_id
from .core import DatasetAdapter, MediaHandle, RecordBatch, SourceDescription

_IMAGE = re.compile(r'val2014/(COCO_val2014_(\d{12})\.jpg)\Z')
_COCO = 'https://s3.amazonaws.com/images.cocodataset.org/val2014/'


class QavaAdapter(DatasetAdapter):
    def probe(self):
        path = Path(self.config['archive'])
        return SourceDescription('qava_author_subset', str(path), path.is_file(), self.revision,
            path.stat().st_size if path.is_file() else None, True, True, True, True, True,
            ('All 1,600 author 32+50 rows; 32 COCO val2014 images on request.',))

    def prepare(self, approved_plan):
        source = super().prepare(approved_plan)
        with Path(self.config['archive']).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != self.config['sha256']:
                raise ValueError('QAVA author archive checksum changed')
        self._records()
        return source

    def _records(self):
        if hasattr(self, '_native_records'):
            return self._native_records
        prefix = self.config['archive_prefix'].rstrip('/') + '/annotation/'
        with tarfile.open(self.config['archive'], 'r:gz') as archive:
            def read(name):
                member = archive.getmember(prefix + name)
                if not member.isfile() or member.size > 4_000_000:
                    raise ValueError('QAVA annotation exceeds byte budget')
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError('QAVA annotation is absent')
                return json.load(stream)
            groups = read('vqa_val_image_32_ques_50.json')
            questions = read('eval_questions_image_32_ques_50.json')
            annotations = read('eval_annotations_image_32_ques_50.json')
        if not isinstance(groups, list) or len(groups) != 32 or questions.get('data_subtype') != 'val2014' or annotations.get('data_subtype') != 'val2014':
            raise ValueError('QAVA author subset shape changed')
        qrows, arows = questions['questions'], annotations['annotations']
        if len(qrows) != 1600 or len(arows) != 1600:
            raise ValueError('QAVA native question or answer count changed')
        qby = {item['question_id']: item for item in qrows}
        aby = {item['question_id']: item for item in arows}
        if len(qby) != 1600 or len(aby) != 1600 or set(qby) != set(aby):
            raise ValueError('QAVA native question and answer IDs do not join')
        records = []; seen = set(); images = set()
        for group in groups:
            ref = group['image']; match = _IMAGE.fullmatch(ref)
            if not match or ref in images or len(group['ques']) != 50:
                raise ValueError('QAVA image group is malformed or duplicated')
            images.add(ref)
            for item in group['ques']:
                qid = item['question_id']
                if qid in seen or qid not in qby or qid not in aby:
                    raise ValueError('QAVA question ID is duplicated or unjoined')
                seen.add(qid)
                if qby[qid]['question'] != item['question'] or qby[qid]['image_id'] != aby[qid]['image_id'] or qby[qid]['image_id'] != int(match[2]):
                    raise ValueError('QAVA grouped question and native VQA rows disagree')
                asset = Asset(id=stable_id(self.dataset.id, self.revision, 'asset', ref),
                    dataset_id=self.dataset.id, release_id=self.revision, modality='image', uri=ref,
                    metadata={'source_dataset': 'COCO val2014', 'source_image_id': qby[qid]['image_id'],
                        'availability': 'official COCO image on request'})
                records.append(Record(id=stable_id(self.dataset.id, self.revision, 'example', str(qid)),
                    dataset_id=self.dataset.id, release_id=self.revision, snapshot_id=self.dataset.snapshot_id,
                    question=item['question'], text=aby[qid]['multiple_choice_answer'],
                    asset_ids=[asset.id], assets=[asset],
                    source={'question_id': qid, 'image_id': qby[qid]['image_id'], 'image': ref,
                        'author_subset': '32 images x 50 questions', 'question_record': qby[qid],
                        'answer_record': aby[qid], '_atlas_origin': {
                            'group_file': prefix + 'vqa_val_image_32_ques_50.json',
                            'question_file': prefix + 'eval_questions_image_32_ques_50.json',
                            'annotation_file': prefix + 'eval_annotations_image_32_ques_50.json'}}))
        if len(records) != 1600 or len(seen) != 1600 or len(images) != 32:
            raise ValueError('QAVA native subset membership changed')
        self._native_records = records; self._images = images
        return records

    @property
    def count(self):
        return len(self._records())

    def source_field_types(self):
        return {'question_id': 'number', 'image_id': 'number', 'image': 'string',
            'author_subset': 'string', 'question_record': 'object', 'answer_record': 'object',
            '_atlas_origin': 'object'}

    def iter_records(self, source, cursor=None, limit=None):
        rows = self._records(); start = int(cursor or 0)
        if not 0 <= start <= len(rows):
            raise ValueError('Invalid QAVA cursor')
        end = min(len(rows), start + min(limit or source.limit, source.limit))
        batch = rows[start:end]
        for row in batch:
            source.charge(len(row.model_dump_json().encode()))
        return RecordBatch(batch, str(end) if end < len(rows) else None, len(batch))

    def resolve_asset(self, source, asset_ref):
        self._records()
        match = _IMAGE.fullmatch(asset_ref)
        if not match or asset_ref not in self._images:
            raise ValueError('QAVA image is absent from pinned subset')
        limit = min(source.max_bytes - source.bytes_read, 10_000_000)
        if limit < 1:
            raise ValueError('QAVA media byte budget exhausted')
        data = bytearray()
        with httpx.stream('GET', _COCO + match[1], timeout=30, follow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200 or int(response.headers.get('Content-Length', 0)) > limit:
                raise ValueError('QAVA COCO original is unavailable or exceeds byte budget')
            etag = response.headers.get('ETag', '').strip('"')
            if not re.fullmatch(r'[a-f0-9]{32}', etag):
                raise ValueError('QAVA COCO original lacks single-object MD5 ETag')
            for chunk in response.iter_bytes(1 << 20):
                data.extend(chunk)
                if len(data) > limit:
                    raise ValueError('QAVA COCO original exceeds byte budget')
        if hashlib.md5(data, usedforsecurity=False).hexdigest() != etag:
            raise ValueError('QAVA COCO original differs from source ETag')
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 50_000_000:
                raise ValueError('QAVA COCO original exceeds pixel budget')
            image.verify()
        source.charge(len(data))
        return MediaHandle(bytes(data), 'image/jpeg', hashlib.sha256(data).hexdigest(), asset_ref)
