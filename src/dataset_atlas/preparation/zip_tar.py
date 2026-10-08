"""Pinned native ZIP/TAR sources, retaining bounded seek indices only."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from dataset_atlas.storage.zip_tar import build_zip_tar_index


def validate_sources(sources):
    if not isinstance(sources,dict) or not 1<=len(sources)<=8:
        raise ValueError('Native ZIP/TAR sources require1..8named archives')
    for key,spec in sources.items():
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',key) or not isinstance(spec,dict):
            raise ValueError('Invalid native ZIP/TAR source name')
        if not re.fullmatch(r'[a-f0-9]{64}',str(spec.get('sha256',''))):
            raise ValueError('Native TAR requires a pinned SHA-256')
        if any(type(spec.get(name)) is not int or not 1<=spec[name]<=50_000_000_000 for name in ('archive_bytes','bytes','compressed_bytes')):
            raise ValueError('Native ZIP/TAR source sizes must be within1byte..50GB')
        if type(spec.get('crc32')) is not int or not 0<=spec['crc32']<=0xffffffff:
            raise ValueError('Native ZIP/TAR requires a pinned member CRC32')
        parsed=urlsplit(spec.get('url',''))
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Native ZIP/TAR source requires credential-free HTTPS')
        if not re.fullmatch(r'"[^"\r\n]+"',str(spec.get('etag',''))):
            raise ValueError('Native parent ZIP requires a pinned strong ETag')
        if not isinstance(spec.get('allowed_hosts'),list) or not spec['allowed_hosts'] or parsed.hostname not in spec['allowed_hosts']:
            raise ValueError('Native parent ZIP requires explicit allowed hosts')
        from dataset_atlas.adapters.core import _safe_relative
        _safe_relative(spec.get('member',''))


def verified_index(path,spec):
    """A recorded full native TAR digest and unchanged derivatives permit reuse."""
    path=Path(path)
    if path.is_symlink() or not (path/'receipt.json').is_file():return None
    proof=json.loads((path/'receipt.json').read_text())
    if (proof.get('format')!='atlas-remote-zip-deflate-tar-v1' or proof.get('source_sha256')!=spec['sha256']
            or not proof.get('whole_native_tar_sha256_checked') or not proof.get('whole_native_zip_member_crc32_checked')
            or {k:v for k,v in proof.get('remote',{}).items() if k!='sha256'}!={k:v for k,v in spec.items() if k!='sha256'}):
        raise ValueError('Saved native ZIP/TAR proof differs from the pinned source')
    if set(proof.get('checksums',{}))!={'members.sqlite','checkpoints.gzidx'}:
        raise ValueError('Saved native ZIP/TAR has an unexpected derivative inventory')
    for name,sha in proof['checksums'].items():
        file=path/name
        if file.is_symlink() or not file.is_file():raise ValueError('Native seek index requires ordinary local files')
        with file.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=sha:raise ValueError('Native seek index checksum changed')
    return proof


def cache_path(root,spec):
    # Seek checkpoints depend on compressed payload bytes and the pinned parent
    # layout, even when two archives have identical decompressed native TARs.
    identity=hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return Path(root)/'work/source-indices/zip-tar'/identity


def register_index(root,path,spec):
    proof=verified_index(path,spec)
    if proof is None:raise ValueError('Cannot register an unfinished native index')
    cache=cache_path(root,spec)
    if cache.exists():
        if verified_index(cache,spec) is None:raise ValueError('Existing native seek cache is incomplete')
        return cache
    cache.parent.mkdir(parents=True,exist_ok=True)
    import tempfile
    with tempfile.TemporaryDirectory(prefix='.native-index-',dir=cache.parent) as temporary:
        stage=Path(temporary)/'index';stage.mkdir()
        for name in proof['checksums']:os.link(Path(path)/name,stage/name)
        (stage/'receipt.json').write_text(json.dumps({**proof,'remote':spec},indent=2)+'\n')
        os.replace(stage,cache)
    return cache


def prepare_sources(root,plan,version,update,check):
    sources=plan['zip_tar_sources'];validate_sources(sources)
    maximum=plan['native_zip_tar_index_bytes'];remaining=maximum;transferred=0;indices={};proofs=[]
    for key,spec in sources.items():
        check();target=Path(version)/'native-audio'/key
        cache=cache_path(root,spec)
        proof=verified_index(target,spec) if target.exists() else None
        reused=proof is not None
        if proof is None and cache.is_dir():
            proof=verified_index(cache,spec)
            target.parent.mkdir(parents=True,exist_ok=True);target.mkdir()
            for name in (*proof['checksums'],'receipt.json'):os.link(cache/name,target/name)
            reused=True
        elif proof is None:
            if target.exists():raise ValueError('Unfinished native ZIP/TAR derivative requires explicit retry cleanup')
            update(stage='indexing native ZIP/TAR audio',current_file=key)
            from dataset_atlas.storage.parallel_ranges import ParallelRangeReader
            proof=build_zip_tar_index(spec,target,max_index_bytes=min(remaining,1_000_000_000),reader_factory=ParallelRangeReader,
                byte_budget=plan['max_download_bytes']-plan['expected_annotation_transfer_bytes']-transferred,
                cancel=check,progress=lambda values:update(current_file=key,downloaded_bytes=transferred+values['network_bytes'],**{k:v for k,v in values.items() if k!='network_bytes'}))
            transferred+=proof['network_bytes']
            register_index(root,target,spec)
        size=sum((target/name).stat().st_size for name in (*proof['checksums'],'receipt.json'))
        remaining-=size
        if remaining<0:raise ValueError('Native audio seek indices exceed aggregate output budget')
        indices[key]=str(target);proofs.append({'language':key,'source_sha256':spec['sha256'],'index_bytes':size,'reused_verified_index':reused})
    return {'indices':indices,'source_transfer_bytes':transferred,'proofs':proofs}
