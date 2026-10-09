"""Native deflated ZIP/TAR access through a virtual gzip envelope.

The envelope is only a seek/decode mechanism. Native TAR and member bytes retain
independent SHA-256 and ZIP CRC proofs; no original is described as a gzip file.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import tarfile
import zipfile
import zlib
from collections import OrderedDict

from .ranges import HttpsRangeReader


class ZipTarReader(io.RawIOBase):
    def __init__(self, spec, *, byte_budget, cache=None, cancel=None, reader_factory=HttpsRangeReader, read_ahead_bytes=1<<20):
        super().__init__()
        if type(read_ahead_bytes) is not int or not 1<=read_ahead_bytes<=16<<20:
            raise ValueError('Virtual source read-ahead must be within1byte..16MiB')
        self.read_ahead_bytes=read_ahead_bytes;self.windows=OrderedDict()
        self.ranges = reader_factory(spec['url'],size=spec['archive_bytes'],etag=spec['etag'],
            allowed_hosts=spec['allowed_hosts'],byte_budget=byte_budget,cache=cache,cancel=cancel)
        try:
            with zipfile.ZipFile(self.ranges) as archive:
                if len(archive.filelist) != len(archive.NameToInfo): raise ValueError('Duplicate native ZIP member names')
                info=archive.getinfo(spec['member'])
                if info.is_dir() or info.compress_type != zipfile.ZIP_DEFLATED or info.flag_bits & 1:
                    raise ValueError('Native source requires an unencrypted deflated TAR member')
                for key,value in [('bytes',info.file_size),('compressed_bytes',info.compress_size),('crc32',info.CRC)]:
                    if type(spec[key]) is not int or spec[key] != value: raise ValueError('Native ZIP/TAR metadata changed')
                if not 1 <= info.file_size <= 50_000_000_000: raise ValueError('Native TAR exceeds50GB source bound')
                self.ranges.seek(info.header_offset)
                header=self.ranges.read(30)
                if len(header)!=30 or header[:4]!=b'PK\x03\x04': raise ValueError('Invalid native ZIP local header')
                flags,method=struct.unpack_from('<HH',header,6)
                namesize,extrasize=struct.unpack_from('<HH',header,26)
                if flags & 1 or method != 8 or namesize > 4096: raise ValueError('Unsupported native ZIP local header')
                name=self.ranges.read(namesize).decode('utf-8' if flags & 2048 else 'cp437')
                if name != info.filename: raise ValueError('Native ZIP local and central names differ')
                self.offset=info.header_offset+30+namesize+extrasize
                if self.offset+info.compress_size > archive.start_dir: raise ValueError('Native ZIP/TAR overlaps directory')
                self.compressed_bytes=info.compress_size
                self.prefix=b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff'
                self.suffix=struct.pack('<II',info.CRC,info.file_size & 0xffffffff)
                self.size=info.compress_size+18;self.position=0
        except BaseException:
            self.ranges.close();raise
    @property
    def bytes_fetched(self): return self.ranges.bytes_fetched
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position
    def seek(self,offset,whence=0):
        position=offset+(self.position if whence==1 else self.size if whence==2 else 0)
        if whence not in (0,1,2) or position < 0: raise ValueError('Invalid virtual gzip seek')
        self.position=position;return position
    def read(self,size=-1):
        if self.closed: raise ValueError('Reader is closed')
        remaining=max(0,self.size-self.position) if size<0 else min(size,max(0,self.size-self.position))
        if remaining > 32_000_000: raise ValueError('Virtual gzip read exceeds32MB per-read bound')
        parts=[]
        while remaining:
            if self.position < 10:
                data=self.prefix[self.position:min(10,self.position+remaining)]
            elif self.position < 10+self.compressed_bytes:
                position=self.position-10;start=position//self.read_ahead_bytes*self.read_ahead_bytes
                if start not in self.windows:
                    count=min(self.read_ahead_bytes,self.compressed_bytes-start)
                    self.ranges.seek(self.offset+start);block=self.ranges.read(count)
                    if len(block)!=count:raise ValueError('Truncated native compressed member')
                    if len(self.windows)>=4:self.windows.popitem(last=False)
                    self.windows[start]=block
                self.windows.move_to_end(start)
                begin=position-start;data=self.windows[start][begin:begin+remaining]
            else:
                start=self.position-10-self.compressed_bytes;data=self.suffix[start:start+remaining]
            if not data: raise ValueError('Truncated virtual gzip source')
            parts.append(data);self.position+=len(data);remaining-=len(data)
        return b''.join(parts)
    def readinto(self,buffer):
        data=self.read(len(buffer));buffer[:len(data)]=data;return len(data)
    def close(self):
        if hasattr(self,'ranges'): self.ranges.close()
        super().close()


class _DigestReader(io.RawIOBase):
    def __init__(self,source):
        super().__init__()
        self.source=source;self.sha=hashlib.sha256();self.bytes=0;self.crc=0;self.indexed_through=0
    def readable(self): return True
    def read(self,size=-1):
        data=self.source.read(size);self.sha.update(data);self.bytes+=len(data);self.crc=zlib.crc32(data,self.crc)
        # Sequential zran reads do not create all intermediate seek states.
        # Extend the index while the compressed read-ahead windows are cached,
        # keeping the raw position unchanged beneath BufferedReader.
        physical=self.source.raw.tell()
        if physical>self.indexed_through:
            self.source.raw.seek(physical-1)
            self.source.raw.seek(physical)
            self.indexed_through=physical
        return data


def build_zip_tar_index(spec, output, *, max_index_bytes=500_000_000, byte_budget,
                        cancel=None, progress=None, reader_factory=HttpsRangeReader):
    """Read all native TAR bytes once, retaining only member hashes and seek states."""
    import indexed_gzip
    from dataset_atlas.adapters.core import _safe_relative
    output=Path(output)
    if output.exists(): raise ValueError('Native ZIP/TAR index already exists')
    if not 1 <= max_index_bytes <= 1_000_000_000: raise ValueError('Invalid native ZIP/TAR index bound')
    output.mkdir(parents=True);members=0;total=0
    try:
        with ZipTarReader(spec,byte_budget=byte_budget,cancel=cancel,reader_factory=reader_factory,read_ahead_bytes=16<<20) as virtual:
            with indexed_gzip.IndexedGzipFile(fileobj=virtual,spacing=4<<20,readbuf_size=16<<20,buffer_size=16<<20) as decoded:
                native=_DigestReader(decoded)
                with sqlite3.connect(output/'members.sqlite') as db:
                    db.execute('CREATE TABLE members(name TEXT PRIMARY KEY,offset INTEGER NOT NULL,bytes INTEGER NOT NULL,sha256 TEXT NOT NULL)')
                    with tarfile.open(fileobj=native,mode='r|') as archive:
                        for info in archive:
                            if cancel: cancel()
                            if info.isdir(): continue
                            if not info.isfile(): raise ValueError('Native TAR has unsupported nonregular member')
                            name=_safe_relative(info.name.removeprefix('./'))
                            if info.offset_data+info.size > spec['bytes']: raise ValueError('Native TAR member exceeds source size')
                            digest=hashlib.sha256();count=0;stream=archive.extractfile(info)
                            if stream is None: raise ValueError('Native TAR member has no readable bytes')
                            with stream:
                                for chunk in iter(lambda:stream.read(1<<20),b''):
                                    if cancel: cancel()
                                    digest.update(chunk);count+=len(chunk)
                            if count != info.size: raise ValueError('Truncated native TAR member')
                            db.execute('INSERT INTO members VALUES(?,?,?,?)',(name,info.offset_data,info.size,digest.hexdigest()))
                            total+=info.size;members+=1
                            if members%100==0:
                                db.commit()
                                if progress: progress({'members':members,'native_bytes':native.bytes,'network_bytes':virtual.bytes_fetched})
                                if (output/'members.sqlite').stat().st_size > max_index_bytes: raise ValueError('Native index exceeds output bound')
                                if (native.bytes//(4<<20)+2)*33000 > max_index_bytes: raise ValueError('Native seek states exceed output bound')
                    while native.read(1<<20):
                        if cancel: cancel()
                        if native.bytes > spec['bytes']: raise ValueError('Native TAR exceeds pinned byte count')
                    db.commit()
                if native.bytes != spec['bytes'] or native.crc != spec['crc32']: raise ValueError('Native TAR byte count or ZIP CRC differs')
                source_sha=native.sha.hexdigest()
                if spec.get('sha256') and source_sha != spec['sha256']: raise ValueError('Native TAR checksum changed')
                # Progressive seeks already built every seek state. Rebuilding
                # would invalidate them and download the complete source again.
                decoded.export_index(str(output/'checkpoints.gzidx'))
                transferred=virtual.bytes_fetched
        checksums={}
        for path in output.iterdir():
            with path.open('rb') as stream: checksums[path.name]=hashlib.file_digest(stream,'sha256').hexdigest()
        size=sum(path.stat().st_size for path in output.iterdir())
        if size>max_index_bytes: raise ValueError('Native index exceeds output bound')
        receipt={'format':'atlas-remote-zip-deflate-tar-v1','source_sha256':source_sha,'source_bytes':spec['bytes'],
            'remote':spec,'members':members,'uncompressed_member_bytes':total,'index_bytes':size,'checksums':checksums,
            'spacing_bytes':4<<20,'indexed_gzip_version':indexed_gzip.__version__,'network_bytes':transferred,
            'whole_native_tar_sha256_checked':True,'whole_native_zip_member_crc32_checked':True,
            'whole_parent_zip_checksum_checked':False,'native_tar_body_retained':False,
            'seek_representation':'Virtual gzip envelope around unchanged native ZIP deflate payload; native TAR/member hashes bind originals.'}
        (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt
    except BaseException:
        import shutil
        shutil.rmtree(output);raise
