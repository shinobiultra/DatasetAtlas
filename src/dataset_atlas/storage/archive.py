"""Bounded, lossless archive repacking for random original-member access."""
from __future__ import annotations
import hashlib
from pathlib import Path
import tarfile
import zipfile


def repack_tar(source, destination, max_bytes, cancel=None):
    """Copy regular TAR members into a stored ZIP; never extract paths or execute data."""
    from dataset_atlas.adapters.core import _safe_relative
    destination=Path(destination)
    temporary=destination.with_suffix('.partial')
    names=set();total=0
    try:
        with tarfile.open(source,'r|*') as archive,zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as output:
            for member in archive:
                if cancel:cancel()
                if member.isdir():continue
                if not member.isfile():raise ValueError('Archive contains a nonregular member')
                name=_safe_relative(member.name.removeprefix('./'))
                if name in names:raise ValueError('Archive contains duplicate member names')
                names.add(name)
                # ZIP overhead includes two copies of each name and ZIP64 headers.
                total+=member.size+2*len(name.encode())+256
                if total>max_bytes:raise ValueError('Repacked archive exceeds approved output budget')
                with archive.extractfile(member) as reader,output.open(name,'w',force_zip64=True) as writer:
                    copied=0
                    while block:=reader.read(1024*1024):
                        if cancel:cancel()
                        copied+=len(block)
                        if copied>member.size:raise ValueError('TAR member exceeds declared size')
                        writer.write(block)
                    if copied!=member.size:raise ValueError('Truncated TAR member')
        if temporary.stat().st_size>max_bytes:raise ValueError('Repacked archive exceeds approved output budget')
        with temporary.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        temporary.replace(destination)
        return {'format':'zip-store','sha256':digest,'bytes':destination.stat().st_size,'members':len(names),
                'note':'Lossless copy of original regular TAR member bytes; filenames preserved.'}
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
