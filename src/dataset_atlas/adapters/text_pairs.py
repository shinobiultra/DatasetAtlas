"""Native ZIP text documents and companion label files, without extraction."""
from __future__ import annotations

import hashlib
from pathlib import Path
import stat
import zipfile

from .core import DatasetAdapter, RecordBatch, SourceDescription, _safe_relative


class TextPairsAdapter(DatasetAdapter):
    def probe(self):
        path = Path(self.config.get('path', ''))
        return SourceDescription('text_pairs', str(path), path.is_file(), self.revision,
            path.stat().st_size if path.is_file() else None, True, True, True, True, False,
            ('Original text and companion labels are read directly from the pinned archive.',))

    def prepare(self, approved_plan):
        source = super().prepare(approved_plan)
        for item in self.config.get('source_files', []):
            with Path(item['path']).open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                    raise ValueError('Native text source checksum changed')
        self._inventory()
        return source

    def _inventory(self):
        if hasattr(self, '_names'):
            return self._names
        with zipfile.ZipFile(self.config['path']) as archive:
            names = set(); total = 0
            for item in archive.infolist():
                if item.is_dir():
                    continue
                name = _safe_relative(item.filename)
                mode = stat.S_IFMT(item.external_attr >> 16)
                if mode and mode != stat.S_IFREG:
                    raise ValueError('Text archive contains a nonregular member')
                if name in names:
                    raise ValueError('Duplicate native text archive member')
                if item.file_size > self.config.get('max_member_bytes', 5_000_000):
                    raise ValueError('Native text member exceeds byte budget')
                names.add(name); total += item.file_size
            if total > self.config.get('max_decoded_bytes', 300_000_000):
                raise ValueError('Native text archive exceeds decoded byte budget')
            text_suffix = self.config.get('text_suffix', '.txt')
            label_suffix = self.config.get('label_suffix', '.lab')
            documents = {name[:-len(text_suffix)] for name in names if name.endswith(text_suffix)}
            labels = {name[:-len(label_suffix)] for name in names if name.endswith(label_suffix)}
            if documents != labels or len(names) != len(documents) * 2:
                raise ValueError('Native text documents and labels do not pair exactly')
        self._names = sorted(documents)
        return self._names

    def source_field_types(self):
        return {'native_id':'string','text':'string','labels':'array','labels_raw':'string',
                'source_members':'object','encoding':'string'}

    def iter_records(self, source, cursor=None, limit=None):
        start = int(cursor or 0)
        if start < 0:
            raise ValueError('Negative text cursor')
        names = self._inventory()
        end = min(len(names), start + min(limit or source.limit, source.limit))
        records = []
        encoding = self.config['encoding']
        with zipfile.ZipFile(self.config['path']) as archive:
            for identity in names[start:end]:
                cancel = getattr(self, 'cancel', None)
                if cancel:
                    cancel()
                text_name = identity + self.config.get('text_suffix', '.txt')
                label_name = identity + self.config.get('label_suffix', '.lab')
                text_bytes, label_bytes = archive.read(text_name), archive.read(label_name)
                source.charge(len(text_bytes) + len(label_bytes))
                text, labels = text_bytes.decode(encoding), label_bytes.decode(encoding)
                row = {'native_id':identity, 'text':text, 'labels_raw':labels,
                       'labels':[label for label in labels.splitlines() if label], 'encoding':encoding,
                       'source_members':{name:{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
                                         for name,data in ((text_name,text_bytes),(label_name,label_bytes))}}
                record = self._record(row, start + len(records))
                source.charge(len(record.model_dump_json().encode()))
                records.append(record)
        return RecordBatch(records, str(end) if end < len(names) else None, len(records))
