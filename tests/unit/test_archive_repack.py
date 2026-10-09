import io,tarfile,zipfile
import pytest
from dataset_atlas.storage.archive import repack_tar


def test_repack_preserves_member_bytes_and_rejects_overbudget_or_links(tmp_path):
    source=tmp_path/'source.tgz'
    with tarfile.open(source,'w:gz') as archive:
        member=tarfile.TarInfo('images/original.jpg');member.size=100
        archive.addfile(member,io.BytesIO(bytes(range(100))))
    target=tmp_path/'derived.zip';receipt=repack_tar(source,target,1000)
    with zipfile.ZipFile(target) as archive:assert archive.read('images/original.jpg')==bytes(range(100))
    assert receipt['members']==1 and receipt['bytes']==target.stat().st_size
    with pytest.raises(ValueError,match='budget'):repack_tar(source,tmp_path/'limited.zip',30)
    assert not (tmp_path/'limited.zip').exists() and not (tmp_path/'limited.partial').exists()
    with tarfile.open(source,'w:gz') as archive:
        link=tarfile.TarInfo('unsafe');link.type=tarfile.SYMTYPE;link.linkname='/etc/passwd';archive.addfile(link)
    with pytest.raises(ValueError,match='nonregular'):repack_tar(source,tmp_path/'linked.zip',1000)


def test_compressed_repack_bounds_decoded_work_and_preserves_native_arrays(tmp_path):
    source=tmp_path/'sparse.tgz';native=b'\0'*2_000_000
    with tarfile.open(source,'w:gz') as archive:
        member=tarfile.TarInfo('mask.npy');member.size=len(native);archive.addfile(member,io.BytesIO(native))
    target=tmp_path/'compressed.zip'
    proof=repack_tar(source,target,10_000,compression='deflate',max_uncompressed_bytes=len(native))
    assert proof['format']=='zip-deflate' and proof['decoded_bytes']==len(native)
    assert proof['bytes']<10_000
    with zipfile.ZipFile(target) as archive:assert archive.read('mask.npy')==native
    with pytest.raises(ValueError,match='decoded byte budget'):
        repack_tar(source,tmp_path/'bomb.zip',10_000,compression='deflate',max_uncompressed_bytes=1000)
    assert not (tmp_path/'bomb.partial').exists()
    with pytest.raises(ValueError,match='explicit decoded'):
        repack_tar(source,tmp_path/'unbounded.zip',10_000,compression='deflate')
    with pytest.raises(ValueError,match='output budget'):
        repack_tar(source,tmp_path/'too-small.zip',800,compression='deflate',max_uncompressed_bytes=len(native))
    assert not (tmp_path/'too-small.partial').exists()
