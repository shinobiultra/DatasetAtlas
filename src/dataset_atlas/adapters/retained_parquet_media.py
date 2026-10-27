"""Existing canonical JSONL rows with lazy, pinned original Parquet image access."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat

from .core import StructuredAdapter, MediaHandle, PreparedSource
from .embedded_parquet import EmbeddedParquetAdapter
from dataset_atlas.storage.local import SafeRoots


def identity(value):
    return (value.st_dev,value.st_ino,value.st_mode,value.st_size,value.st_mtime_ns,value.st_ctime_ns)


class RetainedParquetMediaAdapter(StructuredAdapter):
    def _verify_original(self):
        path=Path(self.config['original_parquet_path']).absolute()
        expected=self.config['original_parquet_sha256'];size=self.config['original_parquet_bytes']
        if (not isinstance(expected,str) or not re.fullmatch(r'[0-9a-f]{64}',expected)
                or type(size) is not int or not 1<=size<=1_000_000_000):
            raise ValueError('Lazy original Parquet requires a bounded length and SHA-256')
        observed=path.lstat()
        if not stat.S_ISREG(observed.st_mode) or observed.st_size!=size:
            raise ValueError('Original Parquet size or file type changed')
        signature=identity(observed)
        if getattr(self,'_original_signature',None)!=signature:
            with SafeRoots({'original':path.parent}).open('original',path.name) as stream:
                if identity(os.fstat(stream.fileno()))!=signature:raise ValueError('Original Parquet identity changed')
                content=hashlib.sha256();read=0
                while True:
                    block=stream.read(min(1<<20,size-read+1))
                    if not block:break
                    read+=len(block)
                    if read>size:raise ValueError('Original Parquet exceeds its pinned byte budget')
                    content.update(block)
                digest=content.hexdigest()
                if identity(os.fstat(stream.fileno()))!=signature or identity(path.lstat())!=signature:
                    raise ValueError('Original Parquet identity changed during verification')
            if digest!=expected:raise ValueError('Original Parquet checksum changed')
            self._original_signature=signature
        return path,signature

    def prepare(self,approved_plan):
        source=super().prepare(approved_plan)
        self._verify_original()
        return source

    def _resolve(self,source,asset_ref,*,decode):
        match=re.fullmatch(r'images/([0-9a-f]{64})\.(jpg|png|webp)',asset_ref)
        row=self.config.get('original_media_rows',{}).get(asset_ref)
        if not match or type(row) is not int or row<0:raise ValueError('Unknown original Parquet image binding')
        path,before=self._verify_original()
        column=self.config.get('original_image_column','image')
        if not isinstance(column,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',column):
            raise ValueError('Invalid original Parquet image column')
        configured=self.dataset.model_copy(deep=True)
        configured.adapter_config={'path':str(path),'sha256':self.config['original_parquet_sha256'],
                                   'media_columns':[column]}
        adapter=EmbeddedParquetAdapter(configured)
        remaining=source.max_bytes-source.bytes_read
        if remaining<1:raise ValueError('Original image exceeds remaining source byte budget')
        original=PreparedSource(source.dataset_id,source.source_revision,remaining,1,str(path))
        resolve=adapter.resolve_asset if decode else adapter.resolve_original_asset
        handle=resolve(original,f'embedded/{row}/0.{match[2]}')
        if identity(path.lstat())!=before:raise ValueError('Original Parquet changed while reading its image')
        if handle.sha256!=match[1]:raise ValueError('Original Parquet image differs from canonical SHA-256 path')
        source.charge(len(handle.data))
        return MediaHandle(handle.data,handle.media_type,handle.sha256,asset_ref)

    def resolve_original_asset(self,source,asset_ref):
        return self._resolve(source,asset_ref,decode=False)

    def resolve_asset(self,source,asset_ref):
        return self._resolve(source,asset_ref,decode=True)
