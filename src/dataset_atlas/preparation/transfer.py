"""Relocate a verified prepared version without changing records or identities."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil

from dataset_atlas.registry import Registry
from . import atomic


def import_prepared_version(root, source_root, dataset_id, *, activate=True):
    root, source_root=Path(root).resolve(),Path(source_root).resolve()
    donor,recipient=Registry(source_root),Registry(root)
    dataset_id=recipient.resolve(dataset_id)
    original=donor.active_directory(dataset_id)
    if original is None:raise ValueError('Source workspace has no active prepared version')
    dataset=donor.dataset(dataset_id);pack=donor.pack(dataset_id)
    if pack.dataset.snapshot_id!=dataset.snapshot_id:raise ValueError('Prepared preview identity changed')
    receipt=json.loads((original/'receipt.json').read_text())
    if receipt['snapshot_id']!=dataset.snapshot_id:raise ValueError('Prepared receipt identity changed')
    if original.name!=receipt['plan_id']:raise ValueError('Prepared receipt plan identity changed')
    for directory,dirs,names in os.walk(original):
        for name in [*dirs,*names]:
            if (Path(directory)/name).is_symlink():raise ValueError('Prepared transfer cannot follow symlinks')
    def verify(path,sha):
        path=Path(path).resolve()
        if not path.is_relative_to(original):raise ValueError('Transfer requires self-contained source and derived files')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=sha:raise ValueError('Prepared transfer checksum changed')
    for relative,sha in pack.checksums.items():
        path=(original/'pack'/relative).resolve()
        if not path.is_relative_to(original/'pack'):raise ValueError('Preview checksum path escapes prepared version')
        verify(path,sha)
    manifest_path=original/'snapshot/manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        for relative,sha in manifest['checksums'].items():
            path=(manifest_path.parent/relative).resolve()
            if not path.is_relative_to(manifest_path.parent):raise ValueError('Snapshot checksum path escapes prepared version')
            verify(path,sha)
    for entry in dataset.adapter_config.get('source_files',[]):
        if entry.get('path'):
            path=Path(entry['path']).resolve()
            if not path.is_relative_to(original):raise ValueError('Transfer requires self-contained native sources')
            verify(path,entry['sha256'])
    if isinstance(dataset.adapter_config.get('sha256'),str) and dataset.adapter_config.get('path'):
        verify(Path(dataset.adapter_config['path']),dataset.adapter_config['sha256'])
    for entry in receipt.get('derived_sources',[]):
        verify(Path(entry['path']),entry['sha256'])
    def relocate(value):
        if isinstance(value,str) and value.startswith(str(source_root)+'/'):
            return str(root/Path(value).relative_to(source_root))
        if isinstance(value,dict):return {key:relocate(item) for key,item in value.items()}
        if isinstance(value,list):return [relocate(item) for item in value]
        return value
    destination=root/'work/prepared'/dataset_id/original.name
    if destination.exists():raise ValueError('Recipient already holds this prepared version')
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging=destination.with_name(destination.name+'.importing')
    if staging.exists():raise ValueError('Prepared transfer staging already exists')
    # Hard links keep one copy of the immutable bytes when workspaces share a
    # filesystem. Metadata is replaced atomically, never written through a link.
    def copy(source,target):
        try:os.link(source,target)
        except OSError:shutil.copy2(source,target)
        return target
    try:
        shutil.copytree(original,staging,copy_function=copy)
        atomic(staging/'dataset.json',relocate(json.loads((original/'dataset.json').read_text())))
        atomic(staging/'receipt.json',relocate(receipt))
        proof={'dataset_id':dataset_id,'snapshot_id':dataset.snapshot_id,'version':original.name,
               'source_workspace':str(source_root),'source_dataset_sha256':hashlib.sha256((original/'dataset.json').read_bytes()).hexdigest(),
               'source_receipt_sha256':hashlib.sha256((original/'receipt.json').read_bytes()).hexdigest(),
               'records_unchanged':True,'activated':activate}
        atomic(staging/'transfer.json',proof)
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging,ignore_errors=True)
        raise
    if activate:atomic(destination.parent/'active.json',{'version':original.name})
    return proof
