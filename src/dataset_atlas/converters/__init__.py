"""Deterministic, reviewable conversions of pinned original files into the records an adapter reads.

Some catalogue datasets are held as a conversion of their originals (a split-preserving Parquet of GLUE TSVs, say). A
recipe that names a converter lets a colleague reproduce that conversion from the same pinned originals. Converters are
trusted code in this repository; nothing from a dataset is ever executed.

A converter must be exactly reproducible: the recipe pins a *row digest* (a hash of the canonical JSON of every produced
row, in order) and the row count, and a fetch fails if either differs. The digest is over row content, not file bytes,
because Parquet encoding differs between library versions.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Callable, Iterable

CONVERTERS: dict[str, Callable] = {}


def converter(name: str):
    def register(function):
        CONVERTERS[name] = function
        return function
    return register


class RowDigest:
    """SHA-256 over the canonical JSON of each row, in order."""
    def __init__(self):
        self._hash, self.count = hashlib.sha256(), 0

    def add(self, row: dict) -> None:
        self._hash.update(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode() + b'\n')
        self.count += 1

    def hexdigest(self) -> str:
        return self._hash.hexdigest()


def file_sha256(path: Path) -> str:
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_rows(rows: Callable[[], Iterable[dict]], output: Path, fmt: str, check=lambda: None, schema=None) -> dict:
    """Write rows (a callable returning a fresh iterator, so the schema can be found first) and digest their content."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == 'jsonl':
        digest = RowDigest()
        with output.open('w') as stream:
            for row in rows():
                check()
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                digest.add(row)
        columns = None
    elif fmt == 'parquet':
        import pyarrow as pa
        import pyarrow.parquet as pq
        if schema is None:
            columns = set()
            for row in rows():
                columns.update(row)
            schema = pa.schema([(column, pa.string()) for column in sorted(columns)])
        ordered = [field.name for field in schema]
        digest = RowDigest()
        with pq.ParquetWriter(output, schema, compression='zstd') as writer:
            batch = []
            for row in rows():
                check()
                normalized = {column: row.get(column) for column in ordered}
                digest.add(normalized)
                batch.append(normalized)
                if len(batch) == 10_000:
                    writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                    batch = []
            if batch:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))
        columns = ordered
    elif fmt == 'csv':
        import csv
        columns = []
        for row in rows():
            columns.extend(c for c in row if c not in columns)
        digest = RowDigest()
        with output.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
            writer.writeheader()
            for row in rows():
                check()
                text = {c: '' if row.get(c) is None else str(row[c]) for c in columns}
                digest.add(text)  # a CSV holds text, so the digest is over what a reader gets back
                writer.writerow(text)
        columns = columns
    else:
        raise ValueError(f'Unsupported converter output format: {fmt}')
    return {'path': output, 'format': fmt, 'count': digest.count, 'rows_sha256': digest.hexdigest(), 'file_sha256': file_sha256(output), 'columns': columns}


def digest_existing(path: Path, fmt: str) -> dict:
    """The row digest of an already-converted file, to pin in a recipe or to compare a conversion against."""
    digest = RowDigest()
    if fmt == 'jsonl':
        for line in Path(path).open():
            if line.strip():
                digest.add(json.loads(line))
    elif fmt == 'csv':
        import csv
        with Path(path).open(newline='', encoding='utf-8-sig') as stream:
            for row in csv.DictReader(stream):
                digest.add(row)
    else:
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches(batch_size=10_000):
            for row in batch.to_pylist():
                digest.add(row)
    return {'count': digest.count, 'rows_sha256': digest.hexdigest()}


def media_digest(directory: Path) -> str:
    """SHA-256 over every file under `directory` (relative path and content hash, sorted): pins extracted media exactly."""
    digest = hashlib.sha256()
    root = Path(directory)
    for path in sorted(p for p in root.rglob('*') if p.is_file()):
        digest.update(f'{path.relative_to(root).as_posix()}\t{file_sha256(path)}\n'.encode())
    return digest.hexdigest()


def run_conversion(spec: dict, inputs: dict[str, Path], output_dir: Path, check=lambda: None) -> dict:
    """Run the named converter and refuse a result that differs from the recipe's pinned count or row digest."""
    from . import text, tables  # noqa: F401  (registers the converters)
    name = spec.get('name')
    if name not in CONVERTERS:
        raise ValueError(f'Unknown converter: {name!r}')
    for key in ('count', 'rows_sha256'):
        if key not in spec:
            raise ValueError(f'A conversion recipe must pin {key}')
    result = CONVERTERS[name](spec.get('params', {}), inputs, Path(output_dir), check)
    if result['count'] != spec['count']:
        raise ValueError(f"Conversion produced {result['count']:,} rows; the recipe pins {spec['count']:,}")
    if result['rows_sha256'] != spec['rows_sha256']:
        raise ValueError('Converted rows differ from the maintainer\'s pinned row digest; the originals or the converter changed')
    # A converter that extracts media returns its directory as adapter_config (e.g. media_root) and a recipe pins its digest.
    if spec.get('media_sha256') and result.get('media_dir') is not None and media_digest(result['media_dir']) != spec['media_sha256']:
        raise ValueError('Extracted media differ from the maintainer\'s pinned media digest; the originals or the converter changed')
    if spec.get('media_sha256') and result.get('media_dir') is None:
        raise ValueError('The recipe pins extracted media but the converter produced none')
    return result
