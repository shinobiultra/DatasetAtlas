"""Stream the author's wide activation CSV as one complete record per SAE neuron."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import tarfile
from pathlib import Path

from . import RowDigest, converter, file_sha256
from .tables import _member


def _activation_rows(source: Path, member: str, value_count: int, check):
    """Preserve the original lexical values; summaries are explicitly Atlas-derived."""
    with tarfile.open(source) as archive, _member(archive, member) as stream:
        reader = csv.reader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline=''))
        header = next(reader, None)
        expected = ['k', *[f'a_{position}' for position in range(1, value_count + 1)]]
        if header is None or header != expected:
            raise ValueError('Native activation header disagrees with k,a_1,...,a_N')
        schema = {'record_unit': 'SAE neuron', 'source_member': member, 'id_column': 'k',
                  'value_columns': {'pattern': 'a_{position}', 'start': 1, 'count': value_count},
                  'header_sha256': hashlib.sha256(','.join(header).encode()).hexdigest(),
                  'header_digest_encoding': 'UTF-8 comma-joined source fields'}
        summary = {'producer': 'Dataset Atlas', 'kind': 'derived',
                   'fields': ['source_row_index', 'value_count', 'values_sha256', 'minimum', 'maximum', 'mean', 'nonzero_count'],
                   'method': 'Source-order row metadata and SHA-256; numeric summaries use Python float values. Original activation strings are unchanged.'}
        seen = set()
        for index, row in enumerate(reader):
            check()
            if len(row) != value_count + 1:
                raise ValueError(f'Native activation row {index} has an invalid width')
            if not row[0]:
                raise ValueError(f'Native activation row {index} has no neuron identifier')
            if row[0] in seen:
                raise ValueError(f'Native activation row {index} has a duplicate neuron identifier')
            seen.add(row[0])
            raw = row[1:]
            try:
                values = [float(value) for value in raw]
            except ValueError:
                raise ValueError(f'Native activation row {index} has a nonnumeric value') from None
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f'Native activation row {index} must contain finite values')
            yield {'k': row[0], 'source_row_index': index, 'value_count': value_count,
                   'activation_values': raw, 'activation_schema': schema,
                   'values_sha256': hashlib.sha256(','.join(raw).encode()).hexdigest(),
                   'minimum': min(values), 'maximum': max(values), 'mean': sum(values) / value_count,
                   'nonzero_count': sum(value != 0 for value in values), 'summary_provenance': summary}


@converter('activation_values')
def activation_values(params, inputs, output_dir, check):
    """Retain each native neuron and every original activation in bounded JSONL."""
    count = params.get('value_count', 50_000)
    budget = params.get('max_output_bytes', 500_000_000)
    if type(count) is not int or not 1 <= count <= 50_000:
        raise ValueError('Activation value_count must be within 1..50000')
    if type(budget) is not int or not 1 <= budget <= 1_000_000_000:
        raise ValueError('Activation output budget must be within 1 byte..1 GB')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / 'activation_values.jsonl'
    digest = RowDigest()
    written = 0
    try:
        with output.open('wb') as stream:
            for row in _activation_rows(inputs['source_tar'], params['member'], count, check):
                payload = json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode() + b'\n'
                written += len(payload)
                if written > budget:
                    raise ValueError('Native activation conversion exceeds its output budget')
                stream.write(payload)
                digest.add(row)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {'path': output, 'format': 'jsonl', 'count': digest.count,
            'rows_sha256': digest.hexdigest(), 'file_sha256': file_sha256(output), 'columns': None,
            'adapter_config': {'mapping': {'id': 'k'}, 'sequential_index': True}}
