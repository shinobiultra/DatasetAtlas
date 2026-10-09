"""Explicitly imported source objects, separate from the evictable download cache."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import tempfile
from .local import SafeRoots


def source_object(root, checksum, size):
    if not checksum or not re.fullmatch(r'[a-f0-9]{64}', checksum):return None
    directory=Path(root)/'work/source-objects'
    if not directory.exists():return None
    path=directory/checksum
    if not path.exists():return None
    with SafeRoots({'sources':directory}).open('sources',checksum) as stream:
        if os.fstat(stream.fileno()).st_size!=size or hashlib.file_digest(stream,'sha256').hexdigest()!=checksum:
            raise ValueError('Registered source differs from its pinned checksum or size')
    return path


def register_source(root, path, checksum, max_bytes):
    """Copy a user-selected file without altering it; never deserialize its contents."""
    if not re.fullmatch(r'[a-f0-9]{64}',checksum):raise ValueError('A SHA-256 checksum is required')
    if type(max_bytes) is not int or not 1<=max_bytes<=10_000_000_000_000:raise ValueError('A positive source byte bound is required')
    path=Path(path).absolute();directory=Path(root)/'work/source-objects';directory.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with SafeRoots({'input':path.parent}).open('input',path.name) as source:
            size=os.fstat(source.fileno()).st_size
            if size>max_bytes:raise ValueError('Source exceeds import byte budget')
            existing=source_object(root,checksum,size)
            if existing:return {'sha256':checksum,'bytes':size,'path':str(existing),'reused':True}
            with tempfile.NamedTemporaryFile(dir=directory,prefix='.import-',delete=False) as output:
                temporary=Path(output.name);digest=hashlib.sha256();count=0
                for chunk in iter(lambda:source.read(4<<20),b''):
                    count+=len(chunk)
                    if count>max_bytes:raise ValueError('Source exceeds import byte budget')
                    output.write(chunk);digest.update(chunk)
                output.flush();os.fsync(output.fileno())
            if count!=size or digest.hexdigest()!=checksum:raise ValueError('Source import checksum or size mismatch')
            target=directory/checksum
            os.replace(temporary,target)
            return {'sha256':checksum,'bytes':size,'path':str(target),'reused':False}
    finally:
        if temporary:temporary.unlink(missing_ok=True)
