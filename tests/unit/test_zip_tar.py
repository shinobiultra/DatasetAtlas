"""Synthetic ZIP/TAR bytes only; validates virtual seek envelope and native hashes."""
import hashlib,io,tarfile,zipfile
import pytest
from dataset_atlas.storage.zip_tar import ZipTarReader,build_zip_tar_index


def fixture():
    data=b'native fixture'*10000
    body=io.BytesIO()
    with tarfile.open(fileobj=body,mode='w') as tar:
        info=tarfile.TarInfo('article/audio.ogg');info.size=len(data);tar.addfile(info,io.BytesIO(data))
    native=body.getvalue();parent=io.BytesIO()
    with zipfile.ZipFile(parent,'w',compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr('English.tar',native)
    with zipfile.ZipFile(io.BytesIO(parent.getvalue())) as archive:info=archive.getinfo('English.tar')
    spec={'url':'https://fixture.invalid/native.zip','archive_bytes':len(parent.getvalue()),'etag':'"fixture"','allowed_hosts':['fixture.invalid'],
          'member':'English.tar','bytes':len(native),'compressed_bytes':info.compress_size,'crc32':info.CRC,'sha256':hashlib.sha256(native).hexdigest()}
    class Reader(io.BytesIO):
        def __init__(self,*args,**kwargs):super().__init__(parent.getvalue());self.bytes_fetched=0
        def read(self,size=-1):
            result=super().read(size);self.bytes_fetched+=len(result);return result
    return spec,Reader,data


def test_native_zip_tar_index_and_random_member_bytes(tmp_path):
    import indexed_gzip
    spec,reader,data=fixture();index=tmp_path/'index'
    proof=build_zip_tar_index(spec,index,byte_budget=1000000,reader_factory=reader)
    assert proof['source_sha256']==spec['sha256'] and proof['members']==1
    assert proof['whole_parent_zip_checksum_checked'] is False and proof['native_tar_body_retained'] is False
    with ZipTarReader(spec,byte_budget=1000000,reader_factory=reader) as virtual:
        with indexed_gzip.IndexedGzipFile(fileobj=virtual,index_file=str(index/'checkpoints.gzidx'),auto_build=False) as decoded:
            decoded.seek(512);assert decoded.read(len(data))==data
    with pytest.raises(ValueError,match='metadata changed'):
        ZipTarReader({**spec,'crc32':0},byte_budget=1000000,reader_factory=reader)
    with pytest.raises(ValueError,match='checksum changed'):
        build_zip_tar_index({**spec,'sha256':'0'*64},tmp_path/'bad',byte_budget=1000000,reader_factory=reader)
    assert not (tmp_path/'bad').exists()


def test_deep_checkpoint_retrieval_verifies_derivatives_and_exact_native_members(tmp_path, monkeypatch):
    import random,sqlite3
    import indexed_gzip
    original_reader=indexed_gzip.IndexedGzipFile
    def single_pass_reader(**kwargs):
        result=original_reader(**kwargs)
        def refuse_rebuild():raise AssertionError('A complete native scan must not trigger another full download')
        result.build_full_index=refuse_rebuild
        return result
    monkeypatch.setattr(indexed_gzip,'IndexedGzipFile',single_pass_reader)
    from dataset_atlas.storage.indexed_tar import read_tar_member
    generator=random.Random(17)
    content={'first.ogg':generator.randbytes(70<<20),'article/late.ogg':generator.randbytes(2<<20)}
    body=io.BytesIO()
    with tarfile.open(fileobj=body,mode='w') as tar:
        for name,data in content.items():
            info=tarfile.TarInfo(name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
    native=body.getvalue();parent=io.BytesIO()
    with zipfile.ZipFile(parent,'w',compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr('English.tar',native)
    with zipfile.ZipFile(io.BytesIO(parent.getvalue())) as archive:info=archive.getinfo('English.tar')
    spec={'url':'https://fixture.invalid/native.zip','archive_bytes':len(parent.getvalue()),'etag':'"fixture"','allowed_hosts':['fixture.invalid'],
          'member':'English.tar','bytes':len(native),'compressed_bytes':info.compress_size,'crc32':info.CRC,'sha256':hashlib.sha256(native).hexdigest()}
    class Reader(io.BytesIO):
        instances=[]
        def __init__(self,*args,**kwargs):
            super().__init__(parent.getvalue());self.bytes_fetched=0;self.budget=kwargs['byte_budget'];self.instances.append(self)
        def read(self,size=-1):
            result=super().read(size);self.bytes_fetched+=len(result)
            if self.bytes_fetched>self.budget:raise ValueError('Synthetic transfer budget exhausted')
            return result
    index=tmp_path/'index';proof=build_zip_tar_index(spec,index,byte_budget=90_000_000,reader_factory=Reader)
    assert proof['members']==2 and proof['checksums']['checkpoints.gzidx']
    assert proof['network_bytes']<spec['compressed_bytes']+1_000_000
    value,receipt=read_tar_member(index,'article/late.ogg',max_bytes=3_000_000,transfer_bytes=10_000_000,reader_factory=Reader)
    assert value==content['article/late.ogg'] and receipt['source_sha256']==spec['sha256']
    assert receipt['transferred_bytes']<len(parent.getvalue())
    with pytest.raises(ValueError,match='byte budget'):
        read_tar_member(index,'first.ogg',max_bytes=100,reader_factory=Reader)
    count=len(Reader.instances)
    with (index/'checkpoints.gzidx').open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='index checksum changed'):
        read_tar_member(index,'article/late.ogg',reader_factory=Reader)
    assert len(Reader.instances)==count
