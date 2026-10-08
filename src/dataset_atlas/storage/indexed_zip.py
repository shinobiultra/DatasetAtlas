"""Checksummed native ZIP members, readable without keeping the whole archive."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import stat
import struct
import zipfile
import zlib


def build_zip_index(source, output, *, source_sha256, remote, max_input_bytes,
                    max_index_bytes=200_000_000, cancel=None, progress=None):
    from dataset_atlas.adapters.core import _safe_relative
    from .indexed_tar import _file_identity
    source, output = Path(source), Path(output)
    if output.exists(): raise ValueError('Original-access index already exists')
    identity = _file_identity(source)
    if source.stat().st_size > max_input_bytes or source.stat().st_size != remote['bytes']:
        raise ValueError('Original ZIP exceeds budget or differs from pinned remote length')
    with source.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != source_sha256:
            raise ValueError('Original ZIP checksum changed')
        stream.seek(0)
        # CPython's ZIP64-aware footer parser avoids allocating an unbounded
        # ZipFile directory before checking its declared size and entry count.
        end = zipfile._EndRecData(stream)  # ty: ignore[unresolved-attribute]
        if end is None or end[zipfile._ECD_SIZE] > max_index_bytes or end[zipfile._ECD_ENTRIES_TOTAL] > 1_000_000:  # ty: ignore[unresolved-attribute]
            raise ValueError('ZIP directory exceeds metadata budget')
    output.mkdir(parents=True)
    count = 0; total = 0
    try:
        with zipfile.ZipFile(source) as archive, source.open('rb') as raw, sqlite3.connect(output/'members.sqlite') as db:
            db.execute('CREATE TABLE members (name TEXT PRIMARY KEY, offset INTEGER NOT NULL, compressed_bytes INTEGER NOT NULL, bytes INTEGER NOT NULL, method INTEGER NOT NULL, sha256 TEXT NOT NULL)')
            for info in archive.infolist():
                if cancel: cancel()
                if info.is_dir(): continue
                name = _safe_relative(info.filename)
                mode = info.external_attr >> 16
                if stat.S_IFMT(mode) and not stat.S_ISREG(mode):
                    raise ValueError('Original ZIP has unsupported nonregular members')
                if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError('Original ZIP uses unsupported encryption or compression')
                # Reading through ZipFile verifies the native header and CRC.
                digest = hashlib.sha256(); size = 0
                with archive.open(info) as member:
                    for chunk in iter(lambda: member.read(1 << 20), b''):
                        if cancel: cancel()
                        size += len(chunk); total += len(chunk); digest.update(chunk)
                        if total > max_input_bytes or size > info.file_size:
                            raise ValueError('Original ZIP decoded content exceeds input budget')
                if size != info.file_size: raise ValueError('Truncated original ZIP member')
                raw.seek(info.header_offset)
                header = raw.read(30)
                if len(header) != 30 or header[:4] != b'PK\x03\x04': raise ValueError('Invalid ZIP member header')
                filename_bytes, extra_bytes = struct.unpack_from('<HH', header, 26)
                offset = info.header_offset + 30 + filename_bytes + extra_bytes
                if offset < 0 or offset + info.compress_size > source.stat().st_size:
                    raise ValueError('ZIP member lies outside original archive')
                db.execute('INSERT INTO members VALUES (?,?,?,?,?,?)',
                           (name, offset, info.compress_size, size, info.compress_type, digest.hexdigest()))
                count += 1
                if count % 1000 == 0:
                    db.commit()
                    if (output/'members.sqlite').stat().st_size > max_index_bytes:
                        raise ValueError('Original ZIP index exceeds metadata budget')
                    if progress: progress({'members': count, 'uncompressed_bytes': total})
            db.commit()
        if _file_identity(source) != identity: raise ValueError('Original ZIP changed during indexing')
        index = output/'members.sqlite'
        if index.stat().st_size > max_index_bytes: raise ValueError('Original ZIP index exceeds metadata budget')
        with index.open('rb') as stream: checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        receipt = {'format': 'atlas-remote-zip-v1', 'source_sha256': source_sha256,
                   'source_bytes': source.stat().st_size, 'remote': remote, 'members': count,
                   'uncompressed_member_bytes': total, 'index_bytes': index.stat().st_size,
                   'checksums': {'members.sqlite': checksum}, 'verified_local_identity': identity}
        (output/'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return receipt
    except BaseException:
        import shutil
        shutil.rmtree(output)
        raise


_VERIFIED = set()


def read_zip_member(index, member, *, max_bytes=50_000_000, transfer_bytes=55_000_000,
                    cache=None, reader_factory=None, cancel=None, on_transfer=None):
    from dataset_atlas.adapters.core import _safe_relative
    from .ranges import HttpsRangeReader
    from .indexed_tar import _file_identity
    index = Path(index).resolve(); member = _safe_relative(member)
    receipt = json.loads((index/'receipt.json').read_text())
    if receipt.get('format') != 'atlas-remote-zip-v1': raise ValueError('Unknown original-access ZIP index format')
    path = index/'members.sqlite'
    key = (str(path), *_file_identity(path), receipt['checksums']['members.sqlite'])
    if key not in _VERIFIED:
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != key[-1]:
                raise ValueError('Original-access ZIP index checksum changed')
        if len(_VERIFIED) >= 32: _VERIFIED.clear()
        _VERIFIED.add(key)
    with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
        row = db.execute('SELECT offset,compressed_bytes,bytes,method,sha256 FROM members WHERE name=?', (member,)).fetchone()
    if row is None: raise FileNotFoundError('Original member is absent from the pinned ZIP')
    offset, compressed_bytes, size, method, sha = row
    remote = receipt['remote']
    if not 0 <= size <= max_bytes or not 0 <= compressed_bytes <= transfer_bytes:
        raise ValueError('Original ZIP member exceeds byte budget')
    if not 0 <= offset <= offset + compressed_bytes <= remote['bytes']:
        raise ValueError('Original ZIP member has invalid bounds')
    options={'size':remote['bytes'],'allowed_hosts':remote['allowed_hosts'],'byte_budget':transfer_bytes,'cache':cache}
    if cancel is not None:options['cancel']=cancel
    if 'block_sha256' in remote:
        from .hash_ranges import HashPinnedRangeReader
        if remote['source_sha256']!=receipt['source_sha256']:raise ValueError('Block manifest differs from original ZIP checksum')
        factory=reader_factory or HashPinnedRangeReader
        options.update(source_sha256=remote['source_sha256'],block_bytes=remote['block_bytes'],block_sha256=remote['block_sha256'])
        fingerprint={'fingerprint_type':'sha256-blocks'}
    else:
        factory=reader_factory or HttpsRangeReader
        options['etag']=remote['etag'];fingerprint={'fingerprint_type':'etag','etag':remote['etag']}
    remote_file=factory(remote['url'],**options)
    try:
        with remote_file:
            remote_file.seek(offset)
            payload = remote_file.read(compressed_bytes)
            transferred = remote_file.bytes_fetched
    finally:
        if on_transfer:on_transfer(remote_file.bytes_fetched)
    if len(payload) != compressed_bytes: raise ValueError('Truncated original ZIP range')
    if method == zipfile.ZIP_STORED:
        data = payload
    elif method == zipfile.ZIP_DEFLATED:
        decoder = zlib.decompressobj(-15)
        data = decoder.decompress(payload, size + 1)
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError('Original ZIP decompression bounds changed')
    else:
        raise ValueError('Unsupported original ZIP compression')
    if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
        raise ValueError('Retrieved original ZIP member checksum changed')
    return data, {'sha256': sha, 'bytes': size, 'transferred_bytes': transferred,
                  'source_sha256': receipt['source_sha256'], **fingerprint}
