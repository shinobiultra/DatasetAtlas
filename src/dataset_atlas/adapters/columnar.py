"""Pinned, sharded Parquet/Arrow releases without executing repository code."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from .core import DatasetAdapter, SourceDescription
from .embedded_parquet import EmbeddedParquetAdapter


class ColumnarAdapter(EmbeddedParquetAdapter):
    def __init__(self, dataset):
        # Image normalization is shared; the manifest pins each shard separately.
        configured = dataset.model_copy(deep=True)
        configured.adapter_config.setdefault('sha256', '0' * 64)
        if 'media_columns' not in configured.adapter_config:
            names = set()
            for entry in configured.adapter_config.get('files', []):
                path = Path(entry['path'])
                if not path.is_file():continue
                if entry.get('format', path.suffix[1:]) == 'parquet':
                    schema = pq.read_schema(path)
                else:
                    with pa.memory_map(str(path), 'r') as stream:
                        try:schema = pa.ipc.open_stream(stream).schema
                        except pa.ArrowInvalid:
                            stream.seek(0);schema = pa.ipc.open_file(stream).schema
                for field in schema:
                    dtype=field.type
                    if pa.types.is_list(dtype) or pa.types.is_large_list(dtype):dtype=dtype.value_type
                    if pa.types.is_struct(dtype) and 'bytes' in [f.name for f in dtype] and 'image' in field.name.lower():names.add(field.name)
            configured.adapter_config['media_columns'] = sorted(names) or ['_atlas_no_embedded_images']
        super().__init__(configured)
        self.files = self.config.get('files', [])
        if not self.files or any(not isinstance(f, dict) or len(f.get('sha256', '')) != 64 for f in self.files):
            raise ValueError('Columnar files require paths and SHA-256 checksums')
        self._counts = None

    def source_field_types(self):
        """Union schemas across every shard, including columns absent from the preview."""
        types = {}
        for entry in self.files:
            if entry.get('format', Path(entry['path']).suffix[1:]) == 'parquet':
                schema = pq.read_schema(entry['path'])
            else:
                with pa.memory_map(entry['path'], 'r') as stream:
                    try: schema = pa.ipc.open_stream(stream).schema
                    except pa.ArrowInvalid:
                        stream.seek(0)
                        schema = pa.ipc.open_file(stream).schema
            for field in schema:
                dtype = field.type
                if pa.types.is_null(dtype):
                    types.setdefault(field.name, set())
                    continue
                kind = ('object' if field.name in self.media_columns and self.config.get('media_encoding') == 'base64'
                        else 'boolean' if pa.types.is_boolean(dtype)
                        else 'number' if pa.types.is_floating(dtype) or (pa.types.is_integer(dtype) and dtype.bit_width <= 32)
                        else 'string' if pa.types.is_string(dtype) or pa.types.is_large_string(dtype)
                        else 'array' if pa.types.is_list(dtype) or pa.types.is_large_list(dtype)
                        else 'object')
                types.setdefault(field.name, set()).add(kind)
        types['_atlas_origin'] = {'object'}
        return {name: next(iter(kinds)) if len(kinds) == 1 else 'object' for name, kinds in types.items()}

    def probe(self):
        paths = [Path(f['path']) for f in self.files]
        return SourceDescription('columnar', str(paths[0]), all(p.is_file() for p in paths),
            self.revision, sum(p.stat().st_size for p in paths if p.is_file()), True, True,
            True, True, True, ('All declared shards; media decoded only when requested.',))

    def prepare(self, plan):
        source = DatasetAdapter.prepare(self, plan)
        for entry in self.files:
            digest = hashlib.sha256()
            with Path(entry['path']).open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != entry['sha256']:
                raise ValueError('Columnar shard differs from pinned checksum')
        return source

    def _batches(self, entry):
        path = Path(entry['path'])
        if entry.get('format', path.suffix[1:]) == 'parquet':
            yield from pq.ParquetFile(path).iter_batches(batch_size=32)
        else:
            with pa.memory_map(str(path), 'r') as stream:
                try:
                    reader = pa.ipc.open_stream(stream)
                except pa.ArrowInvalid:
                    stream.seek(0)
                    reader = pa.ipc.open_file(stream)
                    for i in range(reader.num_record_batches):
                        yield reader.get_batch(i)
                else:
                    yield from reader

    @property
    def count(self):
        if self._counts is None:
            self._counts = [pq.read_metadata(f['path']).num_rows if f.get('format', Path(f['path']).suffix[1:]) == 'parquet'
                            else sum(b.num_rows for b in self._batches(f)) for f in self.files]
        return sum(self._counts)

    def _slice(self, start, limit):
        self.count
        offset = 0
        for entry, count in zip(self.files, self._counts):
            if offset + count <= start:
                offset += count
                continue
            for batch in self._batches(entry):
                if offset + batch.num_rows <= start:
                    offset += batch.num_rows
                    continue
                skip = max(0, start - offset)
                selected = batch.slice(skip, min(limit, batch.num_rows - skip))
                for row in selected.to_pylist():
                    # Reserved provenance lives separately from original source fields.
                    yield row
                limit -= selected.num_rows
                offset += batch.num_rows
                if limit == 0:
                    return

    def _record(self, row, ordinal):
        # Source row ordinals across immutable ordered shards are globally unique.
        self.config['mapping'] = {**self.config.get('mapping', {}), 'id': None}
        if '_atlas_origin' in row:raise ValueError('Source collides with reserved provenance field')
        for key,candidates in {'text':['text','sentence','caption','content'], 'question':['question','Question'], 'choices':['choices','options','Options']}.items():
            if self.config['mapping'].get(key) not in row:
                self.config['mapping'][key]=next((name for name in candidates if name in row),None)
        record = super()._record(row, ordinal)
        offset = 0
        self.count
        for entry, count in zip(self.files, self._counts):
            if ordinal < offset + count:
                record.source['_atlas_origin'] = {'file': entry.get('source_name', Path(entry['path']).name),
                    'row': ordinal - offset, 'sha256': entry['sha256'], 'split': entry.get('split')}
                break
            offset += count
        return record

    def iter_records(self, source, cursor=None, limit=None):
        from .core import RecordBatch
        start = int(cursor or 0)
        if start < 0:
            raise ValueError('Negative cursor')
        records = []
        for ordinal, row in enumerate(self._slice(start, min(limit or source.limit, source.limit)), start):
            record = self._record(row, ordinal)
            source.charge(sum(len(data) for _, _, _, data in self._entries(row) if data) + len(record.model_dump_json().encode()))
            records.append(record)
        end = start + len(records)
        return RecordBatch(records, str(end) if end < self.count else None, len(records))
