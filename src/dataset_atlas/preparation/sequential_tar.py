"""Acquire/index/retire native archives one at a time within declared budgets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

from dataset_atlas.storage import BoundedCache,CacheIdentity,HttpsFetcher
from dataset_atlas.storage.hash_ranges import block_manifest
from dataset_atlas.storage.indexed_tar import build_tar_index,read_tar_member
from . import atomic


def prepare_tar_sources(root,plan,version,update,check):
    """Full publisher checksums, all-member hashes, and cold retrieval precede retirement."""
    directory=version/'native-archives';directory.mkdir(exist_ok=True)
    cache=BoundedCache(version/'staging-download-cache',max(entry['bytes'] for entry in plan['files']))
    indices=[];transferred=0;proofs=[]
    for entry in plan['files']:
        check()
        suffix=entry.get('probe_member_suffix','.JPEG')
        if not isinstance(suffix,str) or not suffix.startswith('.') or not suffix[1:].isalnum() or len(suffix)>12:
            raise ValueError('Native archive probe suffix must name a bounded file extension')
        index=directory/Path(entry['source_name']).stem
        completed=index/'acquisition.json'
        if completed.is_file():
            proof=json.loads(completed.read_text())
            if proof['source']!=entry:raise ValueError('Saved archive checkpoint differs from the plan')
            receipt=json.loads((index/'receipt.json').read_text())
            if receipt['source_sha256']!=proof['source_sha256']:raise ValueError('Saved native index source changed')
            for name in ('members.sqlite','checkpoints.gzidx'):
                if name not in receipt['checksums']:continue
                with (index/name).open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=receipt['checksums'][name]:
                        raise ValueError('Saved native source index checksum changed')
            transferred+=proof.get('transfer',{}).get('network_bytes',entry['bytes'])+sum(p['transferred_bytes'] for p in proof['cold_retrieval'])
            if transferred>plan['max_download_bytes']:raise ValueError('Completed native acquisitions exceed transfer budget')
            indices.append(str(index));proofs.append(proof)
            identity=CacheIdentity(plan.get('revision',plan['prepared_dataset']['release']),entry.get('sha256',entry.get('md5')),'original')
            cache.evict(identity)
            continue
        identity=CacheIdentity(plan.get('revision',plan['prepared_dataset']['release']),entry.get('sha256',entry.get('md5')),'original')
        update(stage='acquiring native archive',current_file=entry['source_name'],downloaded_bytes=transferred)
        from dataset_atlas.storage.parallel_fetch import fetch_checksum_ranges
        source,transfer=fetch_checksum_ranges(entry,cache,identity,allowed_hosts=plan['allowed_hosts'],
            byte_budget=plan['max_download_bytes']-transferred,check=check,
            progress=lambda count:update(stage='acquiring native archive',current_file=entry['source_name'],downloaded_bytes=transferred+count))
        if source.stat().st_size!=entry['bytes']:raise ValueError('Native archive length differs from publisher metadata')
        with source.open('rb') as stream:md5=hashlib.file_digest(stream,'md5').hexdigest()
        if entry.get('md5') and md5!=entry['md5']:raise ValueError('Native archive differs from publisher MD5')
        manifest=block_manifest(source,check=check)
        if entry.get('sha256') and manifest['source_sha256']!=entry['sha256']:raise ValueError('Native archive SHA-256 changed')
        transferred+=transfer['network_bytes']
        remote={'url':entry['url'],'allowed_hosts':plan['allowed_hosts'],**manifest}
        update(stage='indexing native archive',current_file=entry['source_name'],downloaded_bytes=transferred)
        if (index/'receipt.json').exists():
            receipt=json.loads((index/'receipt.json').read_text())
            if receipt['source_sha256']!=manifest['source_sha256']:raise ValueError('Staged native index source changed')
        else:
            receipt=build_tar_index(source,index,source_sha256=manifest['source_sha256'],remote=remote,
                max_uncompressed_bytes=entry.get('max_uncompressed_bytes',entry['bytes']*4),
                max_index_bytes=plan['max_output_bytes']//len(plan['files']),cancel=check,
                progress=lambda values:update(stage='indexing native archive',current_file=entry['source_name'],**values))
        with sqlite3.connect((index/'members.sqlite').as_uri()+'?mode=ro',uri=True) as db:
            pattern='%'+suffix
            total=db.execute('SELECT count(*) FROM members WHERE name LIKE ?',(pattern,)).fetchone()[0]
            if not total:raise ValueError('Native archive has no declared probe members')
            offsets=sorted({0,total//2,total-1})
            probes=[db.execute('SELECT name,sha256 FROM members WHERE name LIKE ? ORDER BY offset LIMIT 1 OFFSET ?',(pattern,position)).fetchone() for position in offsets]
        cold=[]
        for name,sha in probes:
            check()
            remaining=plan['max_download_bytes']-transferred
            if remaining<1:raise ValueError('Native cold retrieval exceeds aggregate transfer budget')
            data,evidence=read_tar_member(index,name,max_bytes=50_000_000,transfer_bytes=min(64_000_000,remaining))
            if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Native cold retrieval changed original bytes')
            transferred+=evidence['transferred_bytes'];cold.append({'member':name,**evidence})
        proof={'source':entry,'source_sha256':manifest['source_sha256'],'publisher_md5_verified':md5 if entry.get('md5') else None,
               'measured_md5':md5,'all_member_count':receipt['members'],'probe_member_suffix':suffix,'probe_member_count':total,
               **({'jpeg_count':total} if suffix=='.JPEG' else {}),'index_bytes':receipt['index_bytes'],
               'cold_retrieval':cold,'transfer':transfer,'retirement':'Complete archive checksum and all-member hashes retained; archive bytes retired after cold checks.'}
        atomic(completed,proof)
        cache.evict(identity)
        indices.append(str(index));proofs.append(proof)
        update(stage='native archive ready',native_archives_completed=len(indices),downloaded_bytes=transferred)
    return {'indices':indices,'source_transfer_bytes':transferred,'acquisition_proofs':proofs}
