"""Native benchmark TSVs with base64 images and within-file image references.

The metadata pass retains byte offsets, not encoded images. Original image
payloads are decoded only when requested; circular-evaluation rows keep their
own IDs and point to the same asset when the source uses a reference.
"""
from __future__ import annotations

import base64
import copy
import csv
import hashlib
import io
from pathlib import Path

from PIL import Image
from .core import DatasetAdapter, SourceDescription, RecordBatch, MediaHandle


class EmbeddedTSVAdapter(DatasetAdapter):
    def __init__(self, dataset):
        super().__init__(dataset)
        self.config = copy.deepcopy(dataset.adapter_config)
        self.max_row_bytes = self.config.get('max_row_bytes', 32_000_000)

    def probe(self):
        paths = [Path(self.config[item['path_key']]) for item in self.config['tables']]
        return SourceDescription('embedded_tsv', str(paths[0]), all(p.is_file() for p in paths), self.revision,
            sum(p.stat().st_size for p in paths if p.is_file()), False, True, True, True, True,
            ('Pinned TSV images are decoded on request; source row references are preserved.',))

    def prepare(self, plan):
        source = super().prepare(plan)
        for entry in self.config.get('source_files', []):
            with Path(entry['path']).open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != entry['sha256']:
                    raise ValueError('TSV source checksum changed')
        self._rows()
        return source

    def _lines(self, stream):
        # csv.reader can consume quoted newlines, while stream.tell() still
        # identifies exact row boundaries. Limit each physical and logical row.
        used = 0
        for line in iter(lambda: stream.readline(self.max_row_bytes + 1), b''):
            used += len(line)
            if used > self.max_row_bytes:
                raise ValueError('TSV row exceeds byte limit')
            text = line.decode('utf-8')
            yield text.removeprefix('\ufeff') if stream.tell() == len(line) else text

    def _read_row(self, stream):
        csv.field_size_limit(max(csv.field_size_limit(), self.max_row_bytes))
        return next(csv.reader(self._lines(stream), delimiter='\t', strict=True), None)

    def _rows(self):
        if hasattr(self, '_metadata_rows'):
            return self._metadata_rows
        rows, locations, references = [], {}, {}
        image_field = self.config.get('image_field', 'image')
        id_field = self.config.get('id_field', 'index')
        for table_index, table in enumerate(self.config['tables']):
            path = Path(self.config[table['path_key']])
            with path.open('rb') as stream:
                header = self._read_row(stream)
                if not header or len(set(header)) != len(header) or any(key not in header for key in (id_field, image_field)):
                    raise ValueError('TSV requires unique columns including index and image')
                ordinal = 0
                while True:
                    start = stream.tell()
                    values = self._read_row(stream)
                    if values is None:
                        break
                    if len(values) != len(header):
                        raise ValueError('TSV row width differs from header')
                    row = dict(zip(header, values))
                    source_id = row[id_field]
                    identity = f'{table_index}/{source_id}'
                    if not source_id or identity in locations or identity in references:
                        raise ValueError('TSV source IDs must be nonempty and unique within a file')
                    encoded = row.pop(image_field)
                    if not encoded:
                        raise ValueError(f'TSV image is empty at {identity}')
                    if encoded.isascii() and encoded.isdecimal():
                        references[identity] = f'{table_index}/{encoded}'
                    else:
                        locations[identity] = (path, start, stream.tell() - start, header.index(image_field))
                    if any(key.startswith('_atlas_') for key in row):
                        raise ValueError('TSV uses reserved Atlas fields')
                    row['_atlas_origin'] = {'identity': identity, 'row': ordinal, 'file': table['path_key'],
                        'split': table['split'], 'language': table.get('language'), 'image_reference': encoded if identity in references else None}
                    row['_atlas_choices'] = [f'{key}. {row[key]}' for key in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if row.get(key)]
                    rows.append(row)
                    ordinal += 1
        for row in rows:
            origin = row['_atlas_origin']['identity']
            target, seen = origin, set()
            while target in references:
                if target in seen:
                    raise ValueError('Cyclic TSV image reference')
                seen.add(target)
                target = references[target]
            if target not in locations:
                raise ValueError(f'Missing TSV image reference for {origin}')
            row['_atlas_media'] = 'tsv/' + target
        self._image_locations = locations
        self._metadata_rows = rows
        return rows

    @property
    def count(self):
        return len(self._rows())

    def iter_records(self, source, cursor=None, limit=None):
        start = int(cursor or 0)
        if start < 0:
            raise ValueError('Negative cursor')
        rows = self._rows()
        end = min(start + min(limit or source.limit, source.limit), len(rows))
        self.config['mapping'] = {'id': '_atlas_origin.identity', 'media': '_atlas_media',
            'question': self.config.get('question_field', 'question'), 'choices': '_atlas_choices'}
        records = []
        for ordinal, row in enumerate(rows[start:end], start):
            record = self._record(row, ordinal)
            record.source.pop('_atlas_media', None)
            record.source.pop('_atlas_choices', None)
            source.charge(len(record.model_dump_json().encode()))
            records.append(record)
        return RecordBatch(records, str(end) if end < len(rows) else None, len(records))

    def resolve_asset(self, source, asset_ref):
        self._rows()
        if not asset_ref.startswith('tsv/') or asset_ref[4:] not in self._image_locations:
            raise ValueError('Unknown TSV image reference')
        path, start, length, image_column = self._image_locations[asset_ref[4:]]
        if length > source.max_bytes - source.bytes_read:
            raise ValueError('TSV image exceeds source byte budget')
        with path.open('rb') as stream:
            stream.seek(start)
            payload = stream.read(length)
        source.charge(len(payload))
        values = self._read_row(io.BytesIO(payload))
        data = base64.b64decode(values[image_column], validate=True)
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 50_000_000:
                raise ValueError('TSV image exceeds pixel budget')
            media_type = Image.MIME[image.format]
            image.verify()
        return MediaHandle(data, media_type, hashlib.sha256(data).hexdigest(), asset_ref)
