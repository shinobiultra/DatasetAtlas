"""Conversions of released CSV tables kept inside a source tarball (the Pach et al. SAE metric benchmark)."""
from __future__ import annotations
import csv
import hashlib
import tarfile
from pathlib import Path
from . import converter, write_rows

MAX_MEMBER_BYTES = 500_000_000


def _member(archive: tarfile.TarFile, name: str) -> tarfile.ExFileObject:
    info = archive.getmember(name)
    if not info.isreg() or info.size > MAX_MEMBER_BYTES:
        raise ValueError(f'{name} is not a regular file within the size limit')
    stream = archive.extractfile(info)
    if stream is None:
        raise ValueError(f'{name} cannot be read from the archive')
    return stream


@converter('tar_csv_member')
def tar_csv_member(params, inputs, output_dir, check):
    """One CSV member of a tarball, unchanged: its rows are exactly what the publisher released."""
    import io
    def rows():
        with tarfile.open(inputs['source_tar']) as archive, _member(archive, params['member']) as stream:
            yield from csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline=''))
    return write_rows(rows, output_dir / Path(params['member']).name, 'csv', check)


@converter('activation_summary')
def activation_summary(params, inputs, output_dir, check):
    """One row per neuron summarising its published activation values (the full 50,000-value rows stay in the source file).

    `values_sha256` is the SHA-256 of the row's values exactly as published, comma-joined, so a summary can be checked against
    the source without redistributing it. Minimum, maximum, mean and the count of non-zero values are computed in double precision."""
    import io
    def rows():
        with tarfile.open(inputs['source_tar']) as archive, _member(archive, params['member']) as stream:
            reader = csv.reader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline=''))
            next(reader)
            for index, row in enumerate(reader):
                raw = row[1:]
                values = [float(value) for value in raw]
                yield {'k': row[0], 'source_row_index': index, 'value_count': len(values),
                       'values_sha256': hashlib.sha256(','.join(raw).encode()).hexdigest(), 'minimum': min(values),
                       'maximum': max(values), 'mean': sum(values) / len(values), 'nonzero_count': sum(1 for v in values if v != 0)}
    return write_rows(rows, output_dir / 'activations_index.csv', 'csv', check)
