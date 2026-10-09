"""Inspect native SAD templates without rendering or running benchmark code."""
from __future__ import annotations

import zipfile

import yaml

from .core import _safe_relative
from .structured_collection import StructuredCollectionAdapter


class SADStructsAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, '_annotation_rows'):
            return self._annotation_rows
        rows = []; consumed = 0
        for spec in self.config['annotations']:
            password = self.config['public_archive_password'].encode('utf-8')
            with zipfile.ZipFile(self.config[spec['path_key']]) as archive:
                names = set()
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    name = _safe_relative(member.filename)
                    if name in names:
                        raise ValueError('Duplicate SAD source member')
                    names.add(name)
                    if not name.startswith('batch/') or not name.endswith('.yaml'):
                        continue
                    cancel = getattr(self, 'cancel', None)
                    if cancel:
                        cancel()
                    consumed += member.file_size
                    if consumed > self.config.get('max_annotation_bytes', 200_000_000):
                        raise ValueError('SAD native templates exceed read budget')
                    value = yaml.load(archive.read(member, pwd=password), Loader=getattr(yaml, 'CSafeLoader', yaml.SafeLoader))
                    if not isinstance(value, dict) or ('samples' in value) == ('trials' in value):
                        raise ValueError('SAD batch must contain exactly samples or trials')
                    key = 'samples' if 'samples' in value else 'trials'
                    records = value[key]
                    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
                        raise ValueError('SAD native batch records must be objects')
                    metadata = {name: data for name, data in value.items() if name != key}
                    for ordinal, item in enumerate(records):
                        if any(name.startswith('_atlas_') for name in item):
                            raise ValueError('SAD source collides with reserved provenance')
                        row = {**item, 'native_record_kind': key, 'native_task': spec['task'],
                               'native_batch': metadata, 'rendering': 'native template; variables not substituted',
                               '_atlas_origin': {'identity': f'{spec["task"]}:{name}:{ordinal}',
                                                 'group': spec['task'], 'split': spec['task'],
                                                 'member': name, 'row': ordinal}, '_atlas_media_refs': []}
                        rows.append(row)
                        if len(rows) > self.config.get('max_records', 200_000):
                            raise ValueError('SAD native record budget exceeded')
        self._annotation_rows = rows
        return rows
