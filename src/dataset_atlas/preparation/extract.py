"""Place named, checksum-pinned members of a verified zip into a directory an adapter reads."""
from __future__ import annotations
import hashlib
from pathlib import Path
import zipfile

MAX_MEMBER_BYTES = 2_000_000_000


def fetch_remote_zip_member(entry,cache,identity,check=lambda:None,*,on_transfer=None):
    """Acquire a pinned native member without downloading its containing archive."""
    from dataset_atlas.adapters.core import _safe_relative
    from dataset_atlas.storage.ranges import HttpsRangeReader
    cached=cache.get(identity)
    if cached:return cached
    spec=entry['remote_zip_member']
    name=_safe_relative(spec['member'])
    budget=spec['transfer_bytes']
    if type(budget) is not int or budget<1 or entry['bytes']>MAX_MEMBER_BYTES:
        raise ValueError('Native ZIP member exceeds declared limits')
    partial=cache.partial_path(identity)
    digest=hashlib.sha256();count=0
    remote=None
    try:
        with HttpsRangeReader(entry['url'],size=spec['archive_bytes'],etag=spec['etag'],
                allowed_hosts=spec['allowed_hosts'],byte_budget=budget,cancel=check,
                credential_profile=spec.get('credential_profile')) as remote,zipfile.ZipFile(remote) as archive:
            if len(archive.namelist())!=len(set(archive.namelist())):raise ValueError('Duplicate native ZIP member names')
            info=archive.getinfo(name)
            if info.is_dir() or info.file_size!=entry['bytes'] or info.CRC!=spec['crc32']:
                raise ValueError('Native ZIP member size or CRC changed')
            with archive.open(info) as stream,partial.open('wb') as out:
                for block in iter(lambda:stream.read(1<<20),b''):
                    check();count+=len(block)
                    if count>entry['bytes']:raise ValueError('Native member exceeds pinned size')
                    out.write(block);digest.update(block)
        if count!=entry['bytes'] or digest.hexdigest()!=entry['sha256']:raise ValueError('Native ZIP member differs from pinned SHA-256')
        return cache.commit(identity,partial,expected_sha256=entry['sha256'],fingerprint_type='sha256',fingerprint=entry['sha256'])
    finally:
        if remote is not None and on_transfer:on_transfer(remote.bytes_fetched)
        partial.unlink(missing_ok=True)


def extract_zip_members(archive: Path, directory: Path, members: list[dict], check=lambda: None) -> None:
    """Copy each pinned member to `directory/<file name>`, failing unless its SHA-256 matches. Nothing else in the zip is read."""
    with zipfile.ZipFile(archive) as zipped:
        for pinned in members:
            check()
            try:
                info = zipped.getinfo(pinned['member'])
            except KeyError as error:
                raise ValueError(f"Pinned member is missing from the archive: {pinned['member']}") from error
            if info.is_dir() or info.file_size > MAX_MEMBER_BYTES:
                raise ValueError(f"Pinned member is not a reasonably sized file: {pinned['member']}")
            target = directory / pinned['member'].rsplit('/', 1)[-1]
            partial = target.with_name(target.name + '.partial')
            digest = hashlib.sha256()
            try:
                with zipped.open(info) as source, partial.open('wb') as out:
                    for block in iter(lambda: source.read(1 << 20), b''):
                        check()
                        digest.update(block)
                        out.write(block)
                if digest.hexdigest() != pinned['sha256']:
                    raise ValueError(f"Archive member differs from its pinned checksum: {pinned['member']}")
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
