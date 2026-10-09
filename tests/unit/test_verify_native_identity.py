"""verify_native_previews compares retained bytes with the strongest native checksum a preview carries, and refuses a preview with none."""
import hashlib
import zlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/verify_native_previews.py'
spec = importlib.util.spec_from_file_location('verify_native_previews', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

DATA = b'original bytes'
SHA256 = hashlib.sha256(DATA).hexdigest()
GIT = hashlib.sha1(f'blob {len(DATA)}\0'.encode() + DATA).hexdigest()


def case(sha256=None, metadata=None, source=None):
    return SimpleNamespace(source=source or {}), SimpleNamespace(sha256=sha256, metadata=metadata or {})


def check(record, asset):
    return module.verify_native_identity(record, asset, DATA, SHA256)


def test_the_assets_own_sha256_wins_and_a_mismatch_is_refused():
    assert check(*case(sha256=SHA256)) == 'asset-sha256'
    with pytest.raises(ValueError, match='native original hash'):
        check(*case(sha256='0' * 64))


def test_a_pinned_git_blob_stands_in_when_the_asset_has_no_sha256():
    check(*case(metadata={'source_checksum': {'git_blob_sha1': GIT}}))
    with pytest.raises(ValueError, match='Git object'):
        check(*case(metadata={'source_checksum': {'git_blob_sha1': '0' * 40}}))


def test_a_native_row_checksum_stands_in_next_and_a_preview_with_nothing_is_refused():
    check(*case(source={'image_sha256': SHA256}))
    with pytest.raises(ValueError, match='native row checksum'):
        check(*case(source={'image_sha256': '1' * 64}))
    with pytest.raises(ValueError, match='no native checksum'):
        check(*case())


def test_a_remote_zip_member_is_accepted_only_with_a_receipt_that_says_there_is_no_independent_hash():
    record, asset = case(metadata={'representation': 'original ZIP member','zip_crc32':zlib.crc32(DATA),
                                  'native_member_bytes':len(DATA),'source_etag':'"native-pinned"'})
    asset.uri = 'zip/val2014/val2014/COCO_val2014_000000000001.jpg'
    assert 'no independent content hash' in check(record, asset)
    asset.uri = 'media/local.jpg'
    with pytest.raises(ValueError, match='no native checksum'):
        check(record, asset)


@pytest.mark.parametrize('defect',['crc','length','marker_only','parent'])
def test_zip_marker_cannot_certify_missing_or_wrong_native_crc_evidence(defect):
    metadata={'representation':'original ZIP member','zip_crc32':zlib.crc32(DATA),'native_member_bytes':len(DATA),'source_etag':'"native"'}
    if defect=='crc':metadata['zip_crc32']^=1
    elif defect=='length':metadata['native_member_bytes']+=1
    elif defect=='parent':metadata.pop('source_etag')
    else:metadata={'representation':'original ZIP member'}
    record,asset=case(metadata=metadata);asset.uri='zip/source/native.png'
    with pytest.raises(ValueError):check(record,asset)
