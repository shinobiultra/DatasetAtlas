"""Release checks select current archives and inspect bounded portable ZIPs."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import zipfile

import pytest


def verifier():
    path = Path(__file__).resolve().parents[2] / 'scripts/verify_distribution.py'
    spec = importlib.util.spec_from_file_location('atlas_distribution_verify', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_archives_ignore_retained_previous_versions(tmp_path):
    module = verifier()
    for version in ('0.2.0', '1.0.0'):
        (tmp_path / f'dataset_atlas-{version}-py3-none-any.whl').touch()
        (tmp_path / f'dataset_atlas-{version}.tar.gz').touch()
    wheel, sdist = module.release_archives(tmp_path, version='1.0.0')
    assert wheel.name == 'dataset_atlas-1.0.0-py3-none-any.whl'
    assert sdist.name == 'dataset_atlas-1.0.0.tar.gz'


def test_current_archive_selection_refuses_a_stale_explicit_wheel(tmp_path):
    module = verifier()
    stale = tmp_path / 'dataset_atlas-0.2.0-py3-none-any.whl'
    stale.touch()
    with pytest.raises(ValueError, match='current|version'):
        module.release_archives(tmp_path, wheel=stale, version='1.0.0')


@pytest.mark.parametrize('name', ['dataset-atlas-sample/../escape.txt', '/absolute.txt', 'other-root/file.txt'])
def test_sample_zip_rejects_escaping_members_before_extraction(tmp_path, name):
    module = verifier()
    archive = tmp_path / 'sample.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr(name, b'synthetic fixture')
    archive.with_name(archive.name + '.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  sample.zip\n')
    with pytest.raises(ValueError, match='path|root|filename'):
        module.inspect_sample_bundle(archive)
    assert not (tmp_path / 'escape.txt').exists()


def test_sample_zip_checks_external_checksum_before_unpacking(tmp_path):
    module = verifier()
    archive = tmp_path / 'sample.zip'
    archive.write_bytes(b'not an archive')
    archive.with_name(archive.name + '.sha256').write_text('0' * 64 + '  sample.zip\n')
    with pytest.raises(ValueError, match='checksum'):
        module.inspect_sample_bundle(archive)


def test_sample_zip_enforces_expanded_budget_before_unpacking(tmp_path):
    module = verifier()
    archive = tmp_path / 'sample.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('dataset-atlas-sample/site/oversized.txt', b'x' * 1024)
    archive.with_name(archive.name + '.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  sample.zip\n')
    with pytest.raises(ValueError, match='budget'):
        module.inspect_sample_bundle(archive, max_bytes=512)
