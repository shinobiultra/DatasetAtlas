"""The pinned Visual6502 revD transistor table, without executing source JavaScript."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import re

from dataset_atlas.models import Record, stable_id
from .core import DatasetAdapter, RecordBatch, SourceDescription


class Visual6502Adapter(DatasetAdapter):
    def probe(self):
        path = Path(self.config['transdefs'])
        return SourceDescription('visual6502_transdefs', str(path), path.is_file(),
            self.revision, path.stat().st_size if path.is_file() else None,
            True, True, True, True, False,
            ('All 3,510 transistors in the pinned 6502 revD source file; exact paper 6507 input is unidentified.',))

    def prepare(self, approved_plan):
        source = super().prepare(approved_plan)
        self._rows()
        return source

    def _rows(self):
        if hasattr(self, '_native_rows'):
            return self._native_rows
        path = Path(self.config['transdefs'])
        if path.stat().st_size != self.config['bytes'] or path.stat().st_size > 2_000_000:
            raise ValueError('Visual6502 source size changed or exceeds budget')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.config['sha256']:
            raise ValueError('Visual6502 source checksum changed')
        decoded = data.decode('utf-8')
        match = re.fullmatch(r'var transdefs\s*=\s*(\[[\s\S]*\])\s*;?\s*', decoded)
        if not match:
            raise ValueError('Visual6502 source is not the expected literal table')
        rows = ast.literal_eval(match[1])
        if not isinstance(rows, list) or len(rows) != 3510:
            raise ValueError('Visual6502 native transistor count changed')
        for index, row in enumerate(rows):
            if (not isinstance(row, list) or len(row) != 6 or row[0] != f't{index}'
                    or any(type(v) is not int or v < 0 for v in row[1:4])
                    or not isinstance(row[4], list) or len(row[4]) != 4
                    or not isinstance(row[5], list) or len(row[5]) != 5
                    or any(type(v) is not int or v < 0 for v in row[4] + row[5])):
                raise ValueError(f'Visual6502 transistor {index} has changed shape')
        self._native_rows = rows
        return rows

    @property
    def count(self):
        return len(self._rows())

    def source_field_types(self):
        return {'transistor_id': 'string', 'gate_node': 'number', 'channel_node_1': 'number',
            'channel_node_2': 'number', 'bounding_box': 'object', 'geometry': 'object',
            '_atlas_origin': 'object'}

    def iter_records(self, source, cursor=None, limit=None):
        rows = self._rows(); start = int(cursor or 0)
        if not 0 <= start <= len(rows):
            raise ValueError('Invalid Visual6502 cursor')
        end = min(len(rows), start + min(limit or source.limit, source.limit))
        records = []
        for transistor_id, gate, c1, c2, bbox, geometry in rows[start:end]:
            record = Record(id=stable_id(self.dataset.id, self.revision, 'transistor', transistor_id),
                dataset_id=self.dataset.id, release_id=self.revision,
                snapshot_id=self.dataset.snapshot_id,
                text=f'{transistor_id}: gate {gate}; channel nodes {c1} and {c2}',
                source={'transistor_id': transistor_id, 'gate_node': gate,
                    'channel_node_1': c1, 'channel_node_2': c2,
                    'bounding_box': bbox, 'geometry': geometry,
                    '_atlas_origin': {'file': 'transdefs.js', 'row': int(transistor_id[1:]),
                        'github_commit': self.config['commit']}})
            source.charge(len(record.model_dump_json().encode()))
            records.append(record)
        return RecordBatch(records, str(end) if end < len(rows) else None, len(records))

    def resolve_asset(self, source, asset_ref):
        raise ValueError('Visual6502 transistor rows have no media asset')
