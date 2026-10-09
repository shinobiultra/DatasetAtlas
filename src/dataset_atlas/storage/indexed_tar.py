"""Bounded original-member retrieval from a pinned remote plain or gzip TAR.

The local checkpoint index is a derivative; the remote archive remains the
original. Every retrieved member is checked against its locally measured SHA-256.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sqlite3
import tarfile
from collections import OrderedDict
import threading


def build_tar_index(source, output, *, source_sha256, remote, max_uncompressed_bytes, max_index_bytes=1_000_000_000, cancel=None, progress=None):
    from dataset_atlas.adapters.core import _safe_relative
    source, output = Path(source), Path(output)
    if output.exists(): raise ValueError('Original-access index already exists')
    with source.open('rb') as stream:
        compressed=stream.read(2)==b'\x1f\x8b'
        stream.seek(0)
        if hashlib.file_digest(stream, 'sha256').hexdigest() != source_sha256:
            raise ValueError('Original archive checksum changed')
    if source.stat().st_size != remote['bytes']:
        raise ValueError('Original archive size differs from pinned remote source')
    if 'parts' in remote and (not remote['parts'] or
                              sum(part['bytes'] for part in remote['parts']) != remote['bytes']):
        raise ValueError('Multipart archive length differs from pinned parts')
    output.mkdir(parents=True)
    total = 0; members = 0
    gzip_reader=None
    try:
        if compressed:
            import indexed_gzip
            gzip_reader=indexed_gzip.IndexedGzipFile(str(source),spacing=4<<20,readbuf_size=1<<20,buffer_size=1<<20)
            decoded_source=gzip_reader
        else:decoded_source=source.open('rb')
        with decoded_source as decoded, sqlite3.connect(output/'members.sqlite') as db:
            db.execute('CREATE TABLE members (name TEXT PRIMARY KEY, offset INTEGER NOT NULL, bytes INTEGER NOT NULL, sha256 TEXT NOT NULL)')
            with tarfile.open(fileobj=decoded, mode='r|') as archive:
                for member in archive:
                    if cancel: cancel()
                    if member.isdir(): continue
                    if not member.isfile(): raise ValueError('Original TAR has unsupported nonregular members')
                    name = _safe_relative(member.name.removeprefix('./'))
                    total += member.size
                    if total > max_uncompressed_bytes or member.offset_data + member.size > max_uncompressed_bytes:
                        raise ValueError('Original TAR exceeds uncompressed byte budget')
                    digest = hashlib.sha256(); count = 0
                    data = archive.extractfile(member)
                    if data is None: raise ValueError('Original TAR member has no readable data')
                    with data:
                        for chunk in iter(lambda: data.read(1 << 20), b''):
                            if cancel: cancel()
                            count += len(chunk); digest.update(chunk)
                    if count != member.size: raise ValueError('Truncated original TAR member')
                    db.execute('INSERT INTO members VALUES (?,?,?,?)', (name, member.offset_data, member.size, digest.hexdigest()))
                    members += 1
                    if members % 1000 == 0:
                        db.commit()
                        if progress: progress({'members': members, 'uncompressed_bytes': total})
                        if (output/'members.sqlite').stat().st_size > max_index_bytes:
                            raise ValueError('Original-access index exceeds byte budget')
                        if compressed and (member.offset_data // (4 << 20) + 2) * 33000 > max_index_bytes:
                            raise ValueError('Gzip checkpoints exceed index byte budget')
            # Drain the gzip trailer so its CRC is verified and the final seek
            # point is present. Native TAR end padding is not a member.
            while decoded.read(1 << 20):
                if cancel: cancel()
                if decoded.tell() > max_uncompressed_bytes:
                    raise ValueError('Original TAR padding exceeds uncompressed byte budget')
            # A stream shorter than the checkpoint spacing may otherwise export
            # an empty index, even after EOF has been read.
            if gzip_reader is not None:
                gzip_reader.build_full_index()
                gzip_reader.export_index(str(output/'checkpoints.gzidx'))
            db.commit()
        size = sum(p.stat().st_size for p in output.iterdir())
        if size > max_index_bytes: raise ValueError('Original-access index exceeds byte budget')
        checksums = {}
        for p in output.iterdir():
            with p.open('rb') as stream: checksums[p.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        receipt = {'format': 'atlas-remote-gzip-tar-v1' if compressed else 'atlas-remote-tar-v1', 'source_sha256': source_sha256,
                   'source_bytes': source.stat().st_size, 'remote': remote, 'members': members,
                   'uncompressed_member_bytes': total, 'index_bytes': size, 'checksums': checksums,
                   'spacing_bytes': (4 << 20) if compressed else None, 'indexed_gzip_version': indexed_gzip.__version__ if compressed else None}
        receipt['verified_local_identity'] = _file_identity(source)
        (output/'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return receipt
    except BaseException:
        # Failed local derivatives can be safely removed; never touch source.
        import shutil
        shutil.rmtree(output)
        raise


def read_tar_member(index, member, *, max_bytes=50_000_000, transfer_bytes=32_000_000, cache=None, reader_factory=None, local_source=None):
    from .ranges import HttpsRangeReader
    from dataset_atlas.adapters.core import _safe_relative
    index = Path(index).resolve(); member = _safe_relative(member)
    receipt = json.loads((index/'receipt.json').read_text())
    if receipt.get('format') not in {'atlas-remote-gzip-tar-v1','atlas-remote-tar-v1','atlas-remote-zip-deflate-tar-v1'}: raise ValueError('Unknown original-access index format')
    # Index verification is cached by file identity, just like local ZIP checksums.
    for name in (('members.sqlite',) if receipt['format']=='atlas-remote-tar-v1' else ('members.sqlite','checkpoints.gzidx')):
        path = index/name; st = path.stat(); key = (str(path), st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, receipt['checksums'][name])
        if key not in _VERIFIED:
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != receipt['checksums'][name]:
                    raise ValueError('Original-access index checksum changed')
            _VERIFIED.clear() if len(_VERIFIED) >= 32 else None
            _VERIFIED.add(key)
    with sqlite3.connect((index/'members.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        row = db.execute('SELECT offset,bytes,sha256 FROM members WHERE name=?', (member,)).fetchone()
    if row is None: raise FileNotFoundError('Original member is absent from the pinned archive')
    offset, size, sha = row
    if not 0 <= size <= max_bytes or offset < 0: raise ValueError('Original member exceeds byte budget')
    if local_source is not None and Path(local_source).is_file() and receipt['format'] != 'atlas-remote-zip-deflate-tar-v1':
        data = _read_local(index, Path(local_source), receipt, offset, size)
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
            raise ValueError('Local original member checksum changed')
        return data, {'sha256': sha, 'bytes': size, 'transferred_bytes': 0,
                      'source_sha256': receipt['source_sha256'], 'source': 'verified local original'}
    remote = receipt['remote']
    if receipt['format']=='atlas-remote-zip-deflate-tar-v1':
        from .zip_tar import ZipTarReader
        if remote.get('sha256') and remote['sha256'] != receipt['source_sha256']:
            raise ValueError('Native ZIP/TAR source checksum differs from index')
        ranges=ZipTarReader(remote,byte_budget=transfer_bytes,cache=cache,**({'reader_factory':reader_factory} if reader_factory else {}))
    elif 'block_sha256' in remote:
        from .hash_ranges import HashPinnedRangeReader
        if remote['source_sha256']!=receipt['source_sha256']:raise ValueError('Block manifest source checksum differs from original')
        factory=reader_factory or HashPinnedRangeReader
        ranges=factory(remote['url'],size=remote['bytes'],source_sha256=remote['source_sha256'],
            block_bytes=remote['block_bytes'],block_sha256=remote['block_sha256'],allowed_hosts=remote['allowed_hosts'],
            byte_budget=transfer_bytes,cache=cache)
    elif 'parts' in remote:
        from .multipart import MultipartRangeReader
        factory = reader_factory or MultipartRangeReader
        ranges = factory(remote['parts'], byte_budget=transfer_bytes, cache=cache)
    else:
        factory = reader_factory or HttpsRangeReader
        ranges = factory(remote['url'], size=remote['bytes'], etag=remote['etag'], allowed_hosts=remote['allowed_hosts'], byte_budget=transfer_bytes, cache=cache)
    with ranges:
        if receipt['format']=='atlas-remote-tar-v1':
            ranges.seek(offset);data=ranges.read(size)
        else:
            import indexed_gzip
            with indexed_gzip.IndexedGzipFile(fileobj=ranges, index_file=str(index/'checkpoints.gzidx'),
                    auto_build=False, readbuf_size=1 << 20, buffer_size=64 << 10) as decoded:
                decoded.seek(offset)
                data = decoded.read(size)
        transferred = ranges.bytes_fetched
    if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
        raise ValueError('Retrieved original member checksum changed')
    identity = ({'fingerprint_type':'sha256-blocks','source_sha256':remote['source_sha256']}
                if 'block_sha256' in remote else {'fingerprint_type': 'multipart-etag', 'part_etags': [part['etag'] for part in remote['parts']]}
                if 'parts' in remote else {'fingerprint_type': 'etag', 'etag': remote['etag']})
    return data, {'sha256': sha, 'bytes': size, 'transferred_bytes': transferred,
                  'source_sha256': receipt['source_sha256'], **identity}


_VERIFIED = set()
_LOCAL_READERS = OrderedDict()
_LOCAL_LOCK = threading.RLock()


def _file_identity(path):
    st = Path(path).stat()
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def _read_local(index, source, receipt, offset, size):
    identity = _file_identity(source)
    key = (str(source.resolve()), *identity, receipt['checksums'].get('checkpoints.gzidx','plain-tar'))
    with _LOCAL_LOCK:
        if key not in _LOCAL_READERS:
            if identity != receipt.get('verified_local_identity'):
                with source.open('rb') as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != receipt['source_sha256']:
                        raise ValueError('Local original archive checksum changed')
                if _file_identity(source) != identity:
                    raise ValueError('Local original changed during verification')
            while len(_LOCAL_READERS) >= 2:
                _, old = _LOCAL_READERS.popitem(last=False)
                old.close()
            if receipt['format']=='atlas-remote-tar-v1':_LOCAL_READERS[key]=source.open('rb')
            else:
                import indexed_gzip
                _LOCAL_READERS[key] = indexed_gzip.IndexedGzipFile(str(source), index_file=str(index/'checkpoints.gzidx'),
                                        auto_build=False, readbuf_size=1 << 20, buffer_size=64 << 10)
        _LOCAL_READERS.move_to_end(key)
        reader = _LOCAL_READERS[key]
        reader.seek(offset)
        return reader.read(size)


class IndexedTarArchive:
    """Read-only ZIP-like view of a native TAR manifest, without repacking media."""
    def __init__(self, index, local_source=None, max_bytes=150_000_000):
        self.index = Path(index).resolve()
        self.local_source = local_source
        self.max_bytes = max_bytes

    def __enter__(self): return self
    def __exit__(self, *args): pass

    def infolist(self):
        import zipfile
        result = []
        with sqlite3.connect((self.index/'members.sqlite').as_uri()+'?mode=ro', uri=True) as db:
            for name, size in db.execute('SELECT name,bytes FROM members ORDER BY name'):
                info = zipfile.ZipInfo(name)
                info.file_size = size
                result.append(info)
        return result

    def getinfo(self, name):
        import zipfile
        with sqlite3.connect((self.index/'members.sqlite').as_uri()+'?mode=ro', uri=True) as db:
            row = db.execute('SELECT bytes FROM members WHERE name=?', (name,)).fetchone()
        if row is None: raise KeyError(name)
        info = zipfile.ZipInfo(name); info.file_size = row[0]
        return info

    def read(self, member):
        name = member if isinstance(member, str) else member.filename
        return read_tar_member(self.index, name, max_bytes=self.max_bytes, local_source=self.local_source)[0]

    def open(self, member):
        import io
        return io.BytesIO(self.read(member))


def route_path(root, dataset_id, snapshot_id):
    identity = hashlib.sha256(json.dumps([dataset_id, snapshot_id], separators=(',', ':')).encode()).hexdigest()
    return Path(root) / 'work/original-access/routes' / (identity + '.json')


def read_original_route(root, dataset_id, snapshot_id, asset_ref, max_bytes, *, transfer_bytes=None):
    """Resolve only a configured archive member; never an arbitrary client URL."""
    path = route_path(root, dataset_id, snapshot_id)
    if not path.is_file(): return None
    config = json.loads(path.read_text())
    if config.get('dataset_id') != dataset_id or config.get('snapshot_id') != snapshot_id:
        raise ValueError('Original-access route identity changed')
    from .cache import BoundedCache
    for entry in config['archives']:
        prefix = entry.get('asset_prefix', '')
        if not asset_ref.startswith(prefix): continue
        base = (Path(root)/'work/original-access').resolve()
        index = (base/entry['index']).resolve()
        if not index.is_relative_to(base): raise ValueError('Original-access index outside configured root')
        try:
            member = entry.get('member_prefix', '') + asset_ref[len(prefix):]
            member = entry.get('member_names', {}).get(member, member)
            reader = read_tar_member
            options = {}
            receipt_path=index/'receipt.json'
            if entry.get('receipt_sha256'):
                if receipt_path.stat().st_size>2_000_000:raise ValueError('Pinned original-access receipt exceeds bounds')
                receipt_bytes=receipt_path.read_bytes()
                if hashlib.sha256(receipt_bytes).hexdigest()!=entry['receipt_sha256']:raise ValueError('Pinned original-access receipt changed')
                kind=json.loads(receipt_bytes).get('format')
            else:kind=json.loads(receipt_path.read_text()).get('format')
            if kind == 'atlas-remote-zip-v1':
                from .indexed_zip import read_zip_member
                reader = read_zip_member
                options['transfer_bytes'] = max_bytes + 1_000_000
            elif kind == 'atlas-remote-parquet-images-v1':
                from .columnar_retention import read_columnar_member
                reader=read_columnar_member
            elif kind == 'atlas-native-cifar-c-v1':
                from .cifar_ranges import read_cifar_row
                reader=read_cifar_row
                options['transfer_bytes']=16_000_000
            if transfer_bytes is not None:
                if type(transfer_bytes) is not int or transfer_bytes<1:raise ValueError('Positive original-route transfer budget required')
                options['transfer_bytes']=min(options.get('transfer_bytes',1_000_000_000 if kind=='atlas-remote-parquet-images-v1' else 32_000_000),transfer_bytes)
            return reader(index, member, max_bytes=max_bytes,
                                   cache=BoundedCache(Path(root)/'work/media-cache/original-ranges', max_bytes=1_000_000_000), **options)
        except FileNotFoundError:
            continue
    return None
