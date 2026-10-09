"""Bounded, lossless archive repacking for random original-member access."""
from __future__ import annotations
import hashlib
from pathlib import Path
import tarfile
import zipfile


def repack_tar(source, destination, max_bytes, cancel=None, *, compression='stored', max_uncompressed_bytes=None):
    """Copy regular TAR members losslessly, with separate encoded/decoded bounds."""
    from dataset_atlas.adapters.core import _safe_relative
    destination=Path(destination)
    temporary=destination.with_suffix('.partial')
    if compression not in {'stored','deflate'}:raise ValueError('Unknown repack compression')
    if compression=='deflate' and (type(max_uncompressed_bytes) is not int or max_uncompressed_bytes<1):
        raise ValueError('Compressed repacking requires an explicit decoded byte budget')
    decoded_limit=max_uncompressed_bytes if max_uncompressed_bytes is not None else max_bytes
    names=set();total=0;decoded=0;headers=0
    try:
        source_args = {'fileobj': source} if hasattr(source, 'read') else {'name': source}
        method=zipfile.ZIP_STORED if compression=='stored' else zipfile.ZIP_DEFLATED
        with tarfile.open(mode='r|*', **source_args) as archive,zipfile.ZipFile(temporary,'w',compression=method,compresslevel=6 if compression=='deflate' else None,allowZip64=True) as output:
            for member in archive:
                if cancel:cancel()
                if member.isdir():continue
                if not member.isfile():raise ValueError('Archive contains a nonregular member')
                name=_safe_relative(member.name.removeprefix('./'))
                if name in names:raise ValueError('Archive contains duplicate member names')
                names.add(name)
                decoded+=member.size
                if decoded>decoded_limit:raise ValueError('Repacked archive exceeds decoded byte budget')
                # ZIP overhead includes two copies of each name and ZIP64 headers.
                total+=member.size+2*len(name.encode())+256
                headers+=2*len(name.encode())+256
                if (compression=='stored' and total>max_bytes) or headers>max_bytes:
                    raise ValueError('Repacked archive exceeds approved output budget')
                reader=archive.extractfile(member)
                if reader is None:raise ValueError('TAR regular member has no readable payload')
                with reader,output.open(name,'w',force_zip64=True) as writer:
                    copied=0
                    while block:=reader.read(1024*1024):
                        if cancel:cancel()
                        copied+=len(block)
                        if copied>member.size:raise ValueError('TAR member exceeds declared size')
                        writer.write(block)
                        if temporary.stat().st_size+headers>max_bytes:
                            raise ValueError('Repacked archive exceeds approved output budget')
                    if copied!=member.size:raise ValueError('Truncated TAR member')
                if temporary.stat().st_size+headers>max_bytes:raise ValueError('Repacked archive exceeds approved output budget')
        if temporary.stat().st_size>max_bytes:raise ValueError('Repacked archive exceeds approved output budget')
        with temporary.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        temporary.replace(destination)
        return {'format':'zip-store' if compression=='stored' else 'zip-deflate','sha256':digest,'bytes':destination.stat().st_size,'members':len(names),'decoded_bytes':decoded,
                'note':'Lossless copy of original regular TAR member bytes; filenames preserved.'}
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
