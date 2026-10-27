"""Synthetic native activation rows retain exact lexical values and their neuron unit."""
from __future__ import annotations

import hashlib
import io
import json
import tarfile

import pytest

from dataset_atlas.converters import RowDigest, run_conversion


def archive(tmp_path, body):
    path = tmp_path / 'source.tar.gz'
    with tarfile.open(path, 'w:gz') as source:
        payload = body.encode()
        member = tarfile.TarInfo('metric_benchmark/activations.csv')
        member.size = len(payload)
        source.addfile(member, io.BytesIO(payload))
    return path


def spec(rows, **params):
    digest = RowDigest()
    for row in rows:
        digest.add(row)
    return {'name': 'activation_values', 'params': {'member': 'metric_benchmark/activations.csv', 'value_count': 3, **params},
            'count': len(rows), 'rows_sha256': digest.hexdigest()}


def expected_row():
    return {'k': 'neuron-7', 'source_row_index': 0, 'value_count': 3,
            'activation_values': ['0.00', '-1e0', '2.500'],
            'activation_schema': {'record_unit': 'SAE neuron', 'source_member': 'metric_benchmark/activations.csv', 'id_column': 'k',
                                  'value_columns': {'pattern': 'a_{position}', 'start': 1, 'count': 3},
                                  'header_sha256': hashlib.sha256(b'k,a_1,a_2,a_3').hexdigest(),
                                  'header_digest_encoding': 'UTF-8 comma-joined source fields'},
            'values_sha256': hashlib.sha256(b'0.00,-1e0,2.500').hexdigest(),
            'minimum': -1.0, 'maximum': 2.5, 'mean': 0.5, 'nonzero_count': 2,
            'summary_provenance': {'producer': 'Dataset Atlas', 'kind': 'derived',
                                   'fields': ['source_row_index', 'value_count', 'values_sha256', 'minimum', 'maximum', 'mean', 'nonzero_count'],
                                   'method': 'Source-order row metadata and SHA-256; numeric summaries use Python float values. Original activation strings are unchanged.'}}


def test_registered_converter_retains_original_strings_and_explicit_derived_summaries(tmp_path):
    source = archive(tmp_path, 'k,a_1,a_2,a_3\nneuron-7,0.00,-1e0,2.500\n')
    want = expected_row()
    result = run_conversion(spec([want]), {'source_tar': source}, tmp_path / 'converted')
    assert result['count'] == 1 and result['format'] == 'jsonl'
    assert json.loads(result['path'].read_text()) == want
    assert result['adapter_config']['sequential_index'] is True
    assert result['adapter_config']['mapping'] == {'id': 'k'}


@pytest.mark.parametrize('body,error', [
    ('k,a_1,a_3,a_2\nn,0,1,2\n', 'header'),
    ('other,a_1,a_2,a_3\nn,0,1,2\n', 'header'),
    ('k,a_1,a_2,a_3\nn,0,1\n', 'width'),
    ('k,a_1,a_2,a_3\nn,0,1,2,3\n', 'width'),
    ('k,a_1,a_2,a_3\nn,0,1,2\nn,3,4,5\n', 'duplicate'),
    ('k,a_1,a_2,a_3\n,0,1,2\n', 'neuron'),
    ('k,a_1,a_2,a_3\nn,0,nan,2\n', 'finite'),
    ('k,a_1,a_2,a_3\nn,0,inf,2\n', 'finite'),
    ('k,a_1,a_2,a_3\nn,0,no-number,2\n', 'numeric'),
])
def test_malformed_native_rows_fail_without_emitting_source_values(tmp_path, body, error):
    source = archive(tmp_path, body)
    with pytest.raises(ValueError, match=error) as caught:
        run_conversion(spec([]), {'source_tar': source}, tmp_path / 'converted')
    assert 'no-number' not in str(caught.value)


def test_converter_enforces_its_output_cap_and_cleans_partial_results(tmp_path):
    source = archive(tmp_path, 'k,a_1,a_2,a_3\nneuron-7,0.00,-1e0,2.500\n')
    with pytest.raises(ValueError, match='output budget'):
        run_conversion(spec([expected_row()], max_output_bytes=16), {'source_tar': source}, tmp_path / 'converted')
    assert not list((tmp_path / 'converted').glob('*.jsonl'))


def test_changed_native_activation_strings_fail_the_pinned_digest(tmp_path):
    source = archive(tmp_path, 'k,a_1,a_2,a_3\nneuron-7,0.0,-1e0,2.500\n')
    with pytest.raises(ValueError, match='pinned row digest'):
        run_conversion(spec([expected_row()]), {'source_tar': source}, tmp_path / 'converted')
