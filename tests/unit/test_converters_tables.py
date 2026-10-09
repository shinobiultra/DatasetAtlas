"""CSV tables kept inside a source tarball are reproduced exactly, and summaries are checkable against their source."""
import csv
import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from dataset_atlas.converters import CONVERTERS, digest_existing, run_conversion
from dataset_atlas.converters import tables  # noqa: F401


def tarball(path: Path, members: dict[str, bytes], extra=None):
    with tarfile.open(path, 'w:gz') as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        for info in extra or []:
            archive.addfile(info)
    return path


def convert(name, params, source, tmp_path):
    result = CONVERTERS[name](params, {'source_tar': source}, tmp_path / name, lambda: None)
    return result


def test_a_csv_member_is_read_unchanged_and_its_digest_matches_a_read_of_the_output(tmp_path):
    source = tarball(tmp_path / 'b.tar.gz', {'bench/pairs.csv': b'k_x,k_y,R_user\n1,2,k_x\n3,4,k_y\n', 'bench/other.csv': b'a\n1\n'})
    result = convert('tar_csv_member', {'member': 'bench/pairs.csv'}, source, tmp_path)
    assert result['count'] == 2 and result['path'].name == 'pairs.csv'
    assert digest_existing(result['path'], 'csv') == {'count': 2, 'rows_sha256': result['rows_sha256']}
    assert list(csv.DictReader(result['path'].open()))[1] == {'k_x': '3', 'k_y': '4', 'R_user': 'k_y'}


def test_a_missing_or_non_regular_member_is_refused(tmp_path):
    link = tarfile.TarInfo('bench/link.csv')
    link.type = tarfile.SYMTYPE
    link.linkname = '/etc/passwd'
    source = tarball(tmp_path / 'b.tar.gz', {'bench/pairs.csv': b'a\n1\n'}, extra=[link])
    with pytest.raises(KeyError):
        convert('tar_csv_member', {'member': 'bench/missing.csv'}, source, tmp_path)
    with pytest.raises(ValueError, match='not a regular file'):
        convert('tar_csv_member', {'member': 'bench/link.csv'}, source, tmp_path)


def test_the_activation_summary_commits_to_the_published_values_without_copying_them(tmp_path):
    raw = [['0', '0.0', '2.5', '0.0'], ['1', '-1.0', '1.0', '3.0']]
    body = 'k,a_1,a_2,a_3\n' + '\n'.join(','.join(r) for r in raw) + '\n'
    source = tarball(tmp_path / 'b.tar.gz', {'bench/activations.csv': body.encode()})
    result = convert('activation_summary', {'member': 'bench/activations.csv'}, source, tmp_path)
    rows = list(csv.DictReader(result['path'].open()))
    assert [r['k'] for r in rows] == ['0', '1'] and rows[0]['value_count'] == '3'
    assert rows[0]['values_sha256'] == hashlib.sha256(b'0.0,2.5,0.0').hexdigest()
    assert (rows[0]['minimum'], rows[0]['maximum'], rows[0]['nonzero_count']) == ('0.0', '2.5', '1')
    assert float(rows[1]['mean']) == pytest.approx(1 + (-1.0 + 1.0 + 3.0) / 3 - 1)
    assert 'a_1' not in rows[0]


def test_changed_originals_fail_the_pinned_digest(tmp_path):
    first = tarball(tmp_path / 'a.tar.gz', {'bench/pairs.csv': b'a\n1\n'})
    pinned = convert('tar_csv_member', {'member': 'bench/pairs.csv'}, first, tmp_path)
    spec = {'name': 'tar_csv_member', 'params': {'member': 'bench/pairs.csv'}, 'count': pinned['count'], 'rows_sha256': pinned['rows_sha256']}
    run_conversion(spec, {'source_tar': first}, tmp_path / 'ok')
    changed = tarball(tmp_path / 'b.tar.gz', {'bench/pairs.csv': b'a\n2\n'})
    with pytest.raises(ValueError, match='differ from the maintainer'):
        run_conversion(spec, {'source_tar': changed}, tmp_path / 'bad')
