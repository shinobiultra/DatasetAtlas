"""Pinned SafeBench release: 2,300 native category/ordinal groups.

The released text, image-prompt, image, and two voice paths share category and
ordinal. The grouping is structural; it is not a claim that prompts are
semantically identical across modalities. Ancillary author scripts and an
extra three-row CSV stay in the original archive, not in executable code.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from dataset_atlas.models import Asset, Record, stable_id
from dataset_atlas.storage.indexed_tar import read_tar_member

from .core import DatasetAdapter, MediaHandle, RecordBatch, SourceDescription, _media_type


class SafeBenchAdapter(DatasetAdapter):
    def _paths(self):
        return (Path(self.config.get('original_archive_path', self.config['path'])),
                Path(self.config['original_access_index']),
                Path(self.config['category_path']))

    def _archive_sha256(self):
        source = next((item for item in self.config.get('source_files', [])
                       if item.get('config_key') == 'path'), None)
        return source['sha256'] if source else self.config['sha256']

    def probe(self):
        archive, index, categories = self._paths()
        exists = (index/'receipt.json').is_file() and categories.is_file()
        return SourceDescription('safebench_pinned_archive', str(archive), exists, self.revision,
                                 archive.stat().st_size if archive.is_file() else None,
                                 True, True, True, True, True,
                                 ('Native category/ordinal grouping; original PNG/WAV bytes from the pinned gzip TAR or bounded remote parts.',))

    def prepare(self, approved_plan):
        source = super().prepare(approved_plan)
        archive, index, categories = self._paths()
        receipt = json.loads((index/'receipt.json').read_text())
        expected = self._archive_sha256()
        if receipt['source_sha256'] != expected:
            raise ValueError('SafeBench archive index differs from pinned source')
        if hashlib.sha256(categories.read_bytes()).hexdigest() != self.config['category_sha256']:
            raise ValueError('SafeBench category inventory changed')
        if archive.is_file():
            with archive.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise ValueError('SafeBench archive changed')
        self._records()
        return source

    def _inventory(self):
        if hasattr(self, '_native_members'):
            return self._native_members
        _, index, _ = self._paths()
        receipt = json.loads((index/'receipt.json').read_text())
        with (index/'members.sqlite').open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != receipt['checksums']['members.sqlite']:
                raise ValueError('SafeBench native member index changed')
        with sqlite3.connect((index/'members.sqlite').as_uri()+'?mode=ro', uri=True) as db:
            members = {name: {'bytes': size, 'sha256': sha}
                       for name, size, sha in db.execute('SELECT name,bytes,sha256 FROM members')}
        self._native_members = members
        return members

    def _csv_rows(self, member, expected):
        archive, index, _ = self._paths()
        info = self._inventory()[member]
        cache = index/'prompt-cache'/info['sha256']
        data = cache.read_bytes() if cache.is_file() else None
        if data is None or len(data) != info['bytes'] or hashlib.sha256(data).hexdigest() != info['sha256']:
            data, _ = read_tar_member(index, member, max_bytes=100_000,
                                      local_source=archive if archive.is_file() else None)
            cache.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=cache.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            try:
                os.replace(temporary, cache)
            finally:
                temporary.unlink(missing_ok=True)
        rows = list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
        if len(rows) != expected or any(len(row) != 1 or not row[0] for row in rows):
            raise ValueError(f'SafeBench native prompt rows differ from pinned release: {member}')
        return [row[0] for row in rows]

    def _records(self):
        if hasattr(self, '_native_records'):
            return self._native_records
        _, _, categories = self._paths()
        with categories.open(newline='', encoding='utf-8-sig') as stream:
            names = {int(row['Index']): row['Category'] for row in csv.DictReader(stream)}
        if set(names) != set(range(1, 24)) or any(not value for value in names.values()):
            raise ValueError('SafeBench category inventory is incomplete')
        members = self._inventory()
        records = []
        for category in range(1, 24):
            text_member = f'final_bench/text/{category}.csv'
            image_prompts = [name for name in members
                             if re.fullmatch(rf'final_bench/image/{category}/[^/]+\.csv', name)
                             and name.rsplit('/', 1)[-1] != 'a1.csv']
            if text_member not in members or len(image_prompts) != 1:
                raise ValueError('SafeBench native prompt files are incomplete or ambiguous')
            image_member = image_prompts[0]
            texts = self._csv_rows(text_member, 100)
            visual_texts = self._csv_rows(image_member, 100)
            for ordinal in range(1, 101):
                media = [
                    ('image', f'final_bench/image/{category}/{ordinal}.png'),
                    ('audio', f'final_bench/audio/audio_data_male/{category}/{ordinal}.wav'),
                    ('audio', f'final_bench/audio/audio_data_female/{category}/{ordinal}.wav'),
                ]
                assets = []
                for modality, member in media:
                    if member not in members:
                        raise ValueError(f'SafeBench native media member is absent: {member}')
                    info = members[member]
                    assets.append(Asset(id=stable_id(self.dataset.id, self.revision, 'asset', member),
                                        dataset_id=self.dataset.id, release_id=self.revision,
                                        modality=modality, uri=member, sha256=info['sha256'],
                                        metadata={'source_member': member, 'original_bytes': info['bytes']}))
                source = {'category_index': category, 'category': names[category], 'ordinal': ordinal,
                          'text_prompt': texts[ordinal-1], 'image_prompt': visual_texts[ordinal-1],
                          '_atlas_origin': {'text_file': text_member, 'text_row': ordinal,
                                            'image_prompt_file': image_member, 'image_prompt_row': ordinal,
                                            'media_files': [member for _, member in media],
                                            'grouping': 'shared native category directory and 1-based ordinal; semantic equivalence unverified'}}
                records.append(Record(id=stable_id(self.dataset.id, self.revision, 'example', f'{category}/{ordinal}'),
                                      dataset_id=self.dataset.id, release_id=self.revision,
                                      snapshot_id=self.dataset.snapshot_id, text=texts[ordinal-1],
                                      asset_ids=[asset.id for asset in assets], assets=assets, source=source))
        self._native_records = records
        return records

    @property
    def count(self):
        return len(self._records())

    def source_field_types(self):
        return {'category_index': 'number', 'category': 'string', 'ordinal': 'number',
                'text_prompt': 'string', 'image_prompt': 'string', '_atlas_origin': 'object'}

    def iter_records(self, source, cursor=None, limit=None):
        rows = self._records()
        start = int(cursor or 0)
        if start < 0 or start > len(rows):
            raise ValueError('Invalid SafeBench cursor')
        end = min(len(rows), start + min(limit or source.limit, source.limit))
        batch = rows[start:end]
        for row in batch:
            source.charge(len(row.model_dump_json().encode()))
        return RecordBatch(batch, str(end) if end < len(rows) else None, len(batch))

    def resolve_asset(self, source, asset_ref):
        members = self._inventory()
        if asset_ref not in members or not re.fullmatch(
            r'final_bench/(?:image/[1-9][0-9]*/[1-9][0-9]*\.png|audio/audio_data_(?:male|female)/[1-9][0-9]*/[1-9][0-9]*\.wav)',
            asset_ref):
            raise ValueError('Asset is absent from SafeBench media inventory')
        archive, index, _ = self._paths()
        data, proof = read_tar_member(index, asset_ref,
                                      max_bytes=source.max_bytes - source.bytes_read,
                                      local_source=archive if archive.is_file() else None)
        source.charge(len(data))
        return MediaHandle(data, _media_type(asset_ref), proof['sha256'], asset_ref)
