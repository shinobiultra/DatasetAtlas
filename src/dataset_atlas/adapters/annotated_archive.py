"""Read original JSON/CSV task annotations inside pinned archives without extraction."""
from __future__ import annotations
import csv
import fnmatch
import io
import json
import tarfile
import zipfile
from .core import DatasetAdapter, DirectoryArchiveAdapter, RecordBatch, _safe_relative, _nested


class AnnotatedArchiveAdapter(DirectoryArchiveAdapter):
    def _rows(self):
        if hasattr(self, '_annotation_rows'):
            return self._annotation_rows
        path = self._path()
        patterns = self.config['annotation_patterns']
        maximum = self.config.get('max_annotation_bytes', 128_000_000)
        rows = []
        consumed = 0
        with (zipfile.ZipFile(path) if zipfile.is_zipfile(path) else tarfile.open(path)) as archive:
            is_zip = isinstance(archive, zipfile.ZipFile)
            members = archive.infolist() if is_zip else archive.getmembers()
            self._member_names = {m.filename if is_zip else m.name for m in members
                                  if (not m.is_dir() if is_zip else m.isfile())}
            selected = sorted((m for m in members if any(fnmatch.fnmatchcase(m.filename if is_zip else m.name, p) for p in patterns)), key=lambda m:m.filename if is_zip else m.name)
            if not selected:
                raise ValueError('No archive annotations matched the declared population')
            names = set()
            for member in selected:
                name = _safe_relative(member.filename if is_zip else member.name)
                if name in names:
                    raise ValueError('Duplicate annotation archive member')
                names.add(name)
                if (is_zip and (member.is_dir() or member.external_attr >> 16 & 0o170000 == 0o120000)) or (not is_zip and not member.isfile()):
                    raise ValueError('Annotation must be a regular archive member')
                consumed += member.file_size if is_zip else member.size
                if consumed > maximum:
                    raise ValueError('Archive annotations exceed configured byte limit')
                with (archive.open(member) if is_zip else archive.extractfile(member)) as stream:
                    text = stream.read(maximum + 1).decode('utf-8-sig')
                if name.endswith('.csv'):
                    values = list(csv.DictReader(io.StringIO(text)))
                elif name.endswith('.jsonl'):
                    values = [json.loads(line) for line in text.splitlines() if line.strip()]
                else:
                    value = json.loads(text)
                    if self.config.get('records_key'):
                        value = _nested(value, self.config['records_key'])
                    mode = self.config.get('json_mode', 'list')
                    values = [value] if mode == 'document' else value
                if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
                    raise ValueError('Archive annotation must yield objects')
                for index, row in enumerate(values):
                    if '_atlas_origin' in row:
                        raise ValueError('Source collides with reserved provenance field')
                    rows.append({**row, '_atlas_origin': {'file':name, 'row':index, 'identity':f'{name}:{index}'}})
        self._annotation_rows = rows
        return rows

    @property
    def count(self):
        return len(self._rows())

    def iter_records(self, source, cursor=None, limit=None):
        start = int(cursor or 0)
        if start < 0:
            raise ValueError('Negative cursor')
        rows = self._rows()
        size = min(limit or source.limit, source.limit)
        # Filenames namespace upstream IDs which may repeat between annotation files.
        self.config['mapping'] = {**self.config.get('mapping', {}), 'id':'_atlas_origin.identity'}
        records = []
        for ordinal, row in enumerate(rows[start:start+size], start):
            record = DatasetAdapter._record(self, row, ordinal)
            prefix = self.config.get('media_prefix', '')
            for asset in record.assets:
                asset.uri = _safe_relative(prefix + asset.uri.removeprefix('./'))
                if asset.uri not in self._member_names:
                    raise ValueError(f'Annotation references missing media: {asset.uri}')
            source.charge(len(record.model_dump_json().encode()))
            records.append(record)
        end = start + len(records)
        return RecordBatch(records, str(end) if end < len(rows) else None, len(records))
