"""HTTPS ranges verified against blocks measured from a complete original.

A source without ETags can still support safe random access when every fetched
block is checked against its SHA-256. The complete original is hashed locally;
source receipts distinguish independent publisher checksums from measured
digests of author-linked downloads. No HTTP header is treated as a checksum.
"""
from __future__ import annotations

import hashlib
import io
import re
import time
from urllib.parse import urljoin

from .cache import CacheIdentity
from .https import HttpsFetcher,_PinnedHTTPSConnection


def block_manifest(path,block_bytes=8<<20,check=lambda:None):
    blocks=[];full=hashlib.sha256();size=0
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(block_bytes),b''):
            check();blocks.append(hashlib.sha256(data).hexdigest());full.update(data);size+=len(data)
    return {'bytes':size,'source_sha256':full.hexdigest(),'block_bytes':block_bytes,'block_sha256':blocks}


class HashPinnedRangeReader(io.RawIOBase):
    def __init__(self,url,*,size,source_sha256,block_bytes,block_sha256,allowed_hosts,byte_budget,cache=None,cancel=None):
        super().__init__()
        if type(size) is not int or size<1 or type(block_bytes) is not int or not 1<=block_bytes<=32_000_000:
            raise ValueError('Invalid hash-pinned source size or block size')
        if type(byte_budget) is not int or byte_budget<1:raise ValueError('Positive range transfer budget required')
        if not re.fullmatch('[a-f0-9]{64}',source_sha256) or len(block_sha256)!=(size+block_bytes-1)//block_bytes:
            raise ValueError('Invalid complete block hash manifest')
        if any(not re.fullmatch('[a-f0-9]{64}',value) for value in block_sha256):raise ValueError('Invalid source block SHA-256')
        self.url=url;self.size=size;self.source_sha256=source_sha256;self.block_bytes=block_bytes;self.hashes=block_sha256
        self.position=0;self.bytes_fetched=0;self.byte_budget=byte_budget;self.cache=cache;self.cancel=cancel
        self.fetcher=HttpsFetcher(allowed_hosts,timeout=45,max_bytes=byte_budget)
        self._last=None

    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        position=offset+(self.position if whence==1 else self.size if whence==2 else 0)
        if whence not in (0,1,2) or position<0:raise ValueError('Invalid remote seek')
        self.position=position;return position
    def readinto(self,buffer):
        data=self.read(len(buffer));buffer[:len(data)]=data;return len(data)
    def read(self,size=-1):
        if self.closed:raise ValueError('Reader is closed')
        count=max(0,self.size-self.position) if size<0 else min(size,max(0,self.size-self.position))
        if count>self.byte_budget:raise ValueError('Remote read exceeds byte budget')
        chunks=[];remaining=count
        while remaining:
            index,within=divmod(self.position,self.block_bytes)
            data=self._block(index);take=min(remaining,len(data)-within)
            chunks.append(data[within:within+take]);self.position+=take;remaining-=take
        return b''.join(chunks)

    def _block(self,index):
        if self.cancel:self.cancel()
        if self._last is not None and self._last[0]==index:return self._last[1]
        digest=self.hashes[index];start=index*self.block_bytes;end=min(self.size,start+self.block_bytes)-1
        identity=CacheIdentity(self.source_sha256,digest,'verified-source-block-v1')
        data=None
        if self.cache:
            path=self.cache.get(identity)
            if path:
                try:data=path.read_bytes()
                except FileNotFoundError:pass
        if data is None:
            count=end-start+1
            if self.bytes_fetched+count>self.byte_budget:raise ValueError('Verified blocks exceed transfer budget')
            data=self._fetch(start,end)
        if len(data)!=end-start+1 or hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError('Source block differs from pinned SHA-256')
        if self.cache and len(data)<=self.cache.max_bytes and self.cache.get(identity) is None:
            import fcntl
            with (self.cache.root/'hash-range.lock').open('a') as lock:
                deadline=time.monotonic()+30
                while True:
                    if self.cancel:self.cancel()
                    try:
                        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                    except BlockingIOError:
                        if time.monotonic()>=deadline:raise ValueError('Hash-range cache writer exceeded wait bound')
                        time.sleep(.05)
                if self.cancel:self.cancel()
                if self.cache.get(identity) is None:
                    partial=self.cache.partial_path(identity);partial.write_bytes(data)
                    self.cache.commit(identity,partial,expected_sha256=digest,fingerprint_type='sha256',fingerprint=digest)
        if self.cancel:self.cancel()
        self._last=(index,data)
        return data

    def _fetch(self,start,end):
        current=self.url
        for _ in range(self.fetcher.max_redirects+1):
            if self.cancel:self.cancel()
            host,port,address,target=self.fetcher._destination(current)
            connection=_PinnedHTTPSConnection(host,address,port,self.fetcher.timeout)
            try:
                connection.request('GET',target,headers={'Accept-Encoding':'identity','Range':f'bytes={start}-{end}','User-Agent':'DatasetAtlas/0.2'})
                response=connection.getresponse()
                if response.status in (301,302,303,307,308):
                    location=response.getheader('Location')
                    if not location:raise ValueError('Range redirect has no location')
                    current=urljoin(current,location);continue
                if response.status!=206:raise ValueError(f'Hash-pinned source requires HTTP 206; received {response.status}')
                if response.getheader('Content-Encoding','identity')!='identity':raise ValueError('Encoded source range is unsupported')
                if response.getheader('Content-Range')!=f'bytes {start}-{end}/{self.size}':raise ValueError('Source bounds or length changed')
                if response.getheader('Content-Length')!=str(end-start+1):raise ValueError('Source range length changed')
                chunks=[];count=0
                while count<=end-start+1:
                    if self.cancel:self.cancel()
                    block=response.read(min(1<<20,end-start+2-count))
                    if not block:break
                    chunks.append(block);count+=len(block);self.bytes_fetched+=len(block)
                    if self.bytes_fetched>self.byte_budget:raise ValueError('Verified blocks exceed transfer budget')
                if count!=end-start+1:raise ValueError('Source range payload length changed')
                return b''.join(chunks)
            finally:connection.close()
        raise ValueError('Too many source range redirects')
