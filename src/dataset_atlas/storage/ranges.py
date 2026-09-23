"""Bounded, revision-bound HTTPS range reads for selective archive/media access."""
from __future__ import annotations
import hashlib
import http.client
import io
from pathlib import Path
import re
from urllib.parse import urljoin
from .https import HttpsFetcher, _PinnedHTTPSConnection
from .cache import BoundedCache, CacheIdentity


class HttpsRangeReader(io.RawIOBase):
    """Seekable HTTPS file. A server ignoring Range never triggers a full download.

    Strong ETags are consistency fingerprints, not cryptographic content hashes.
    The caller pins the length/ETag and separately records hashes of fetched media.
    """
    def __init__(self, url, *, size, etag, allowed_hosts, byte_budget, cache=None, cancel=None):
        super().__init__()
        if type(size) is not int or size < 1 or type(byte_budget) is not int or byte_budget < 1:
            raise ValueError('Range source requires positive size and byte budget')
        if not isinstance(etag,str) or not re.fullmatch(r'"[^"\r\n]+"',etag):
            raise ValueError('Range source requires a pinned strong ETag')
        self.url=url;self.size=size;self.etag=etag;self.byte_budget=byte_budget
        self._resolved_url=None
        self._connection=None
        self._connection_origin=None
        self.position=0;self.bytes_fetched=0;self.cache=cache;self.cancel=cancel
        self.fetcher=HttpsFetcher(allowed_hosts,timeout=30,max_bytes=byte_budget)

    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def close(self):
        connection=getattr(self,'_connection',None)
        if connection is not None:
            connection.close()
            self._connection=None
        super().close()
    def seek(self,offset,whence=0):
        position=offset+(self.position if whence==1 else self.size if whence==2 else 0)
        if whence not in (0,1,2) or position<0:raise ValueError('Invalid remote seek')
        self.position=position
        return position

    def readinto(self,buffer):
        data=self.read(len(buffer));buffer[:len(data)]=data
        return len(data)

    def read(self,size=-1):
        if self.closed:raise ValueError('Reader is closed')
        count=max(0,self.size-self.position) if size<0 else min(size,max(0,self.size-self.position))
        if not count:return b''
        if count>self.byte_budget:raise ValueError('Remote range exceeds read budget')
        start=self.position;end=start+count-1
        identity=CacheIdentity(self.etag,hashlib.sha256(f'{self.url}:{self.size}:{start}:{end}'.encode()).hexdigest(),'https-range-v1')
        data=None
        if self.cache:
            # A concurrent shard reader may evict an object between get() and
            # read_bytes(). Use the same short lock as cache commits.
            import fcntl
            with (self.cache.root/'range-cache.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                path=self.cache.get(identity)
                if path:
                    if path.stat().st_size!=count:raise ValueError('Cached range length mismatch')
                    data=path.read_bytes()
        if data is None:
            if self.bytes_fetched+count>self.byte_budget:raise ValueError('Remote reads exceed transfer budget')
            data=self._fetch(start,end)
            self.bytes_fetched+=len(data)
            if self.cache:
                # Independent readers may request the same immutable range concurrently.
                import fcntl
                lock_path=self.cache.root/'range-cache.lock'
                with lock_path.open('a') as lock:
                    fcntl.flock(lock,fcntl.LOCK_EX)
                    if self.cache.get(identity) is None:
                        partial=self.cache.partial_path(identity);partial.write_bytes(data)
                        self.cache.commit(identity,partial,fingerprint_type='etag',fingerprint=self.etag)
        self.position+=len(data)
        return data

    def _fetch(self,start,end):
        current=self._resolved_url or self.url
        reconnected=False
        for _ in range(self.fetcher.max_redirects+1):
            if self.cancel:self.cancel()
            host,port,address,target=self.fetcher._destination(current)
            origin=(host,port)
            reused=self._connection is not None and self._connection_origin==origin
            if not reused:
                if self._connection is not None:self._connection.close()
                self._connection=_PinnedHTTPSConnection(host,address,port,self.fetcher.timeout)
                self._connection_origin=origin
            connection=self._connection
            keep=False
            try:
                try:
                    connection.request('GET',target,headers={'Accept-Encoding':'identity','Range':f'bytes={start}-{end}',
                                                           'If-Match':self.etag,'User-Agent':'DatasetAtlas/0.1'})
                    response=connection.getresponse()
                except (http.client.RemoteDisconnected,BrokenPipeError,ConnectionResetError):
                    # Retry a stale keep-alive socket once, before consuming any
                    # response body. Partial payload failures are never retried.
                    if not reused or reconnected:raise
                    reconnected=True
                    continue
                if response.status in (301,302,303,307,308):
                    location=response.getheader('Location')
                    if not location:raise ValueError('Range redirect has no location')
                    current=urljoin(current,location)
                    continue
                if response.status in (401,403) and current!=self.url and self._resolved_url:
                    # Signed CDN destinations can expire; resolve again once.
                    self._resolved_url=None;current=self.url
                    continue
                if response.status!=206:raise ValueError(f'Range source requires HTTP 206; received {response.status}')
                if response.getheader('ETag')!=self.etag:raise ValueError('Range source ETag changed')
                if response.getheader('Content-Encoding','identity')!='identity':raise ValueError('Encoded range response is unsupported')
                expected=f'bytes {start}-{end}/{self.size}'
                if response.getheader('Content-Range')!=expected:raise ValueError('Range response bounds or source length changed')
                count=end-start+1
                if response.getheader('Content-Length') is not None and response.getheader('Content-Length')!=str(count):
                    raise ValueError('Range Content-Length disagrees with request')
                data=response.read(count+1)
                if len(data)!=count:raise ValueError('Range response is truncated or overlong')
                self._resolved_url=current
                keep=not getattr(response,'will_close',True)
                return data
            finally:
                if not keep:
                    connection.close()
                    self._connection=None
        raise ValueError('Too many HTTPS range redirects')


def range_fingerprint(url, *, expected_size, allowed_hosts):
    """Resolve a public source's strong ETag without reading its body."""
    fetcher=HttpsFetcher(allowed_hosts,timeout=30)
    current=url
    for _ in range(fetcher.max_redirects+1):
        host,port,address,target=fetcher._destination(current)
        connection=_PinnedHTTPSConnection(host,address,port,fetcher.timeout)
        try:
            connection.request('HEAD',target,headers={'Accept-Encoding':'identity'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location:raise ValueError('Source redirect has no location')
                current=urljoin(current,location)
                continue
            if response.status!=200:raise ValueError(f'Source fingerprint HTTP {response.status}')
            if response.getheader('Content-Length')!=str(expected_size):raise ValueError('Remote source length changed')
            etag=response.getheader('ETag')
            if not etag or not re.fullmatch(r'"[^"\r\n]+"',etag):raise ValueError('Remote source has no strong ETag')
            return etag
        finally:connection.close()
    raise ValueError('Too many source fingerprint redirects')


class SmallReadBuffer(io.RawIOBase):
    """Coalesce neighbouring small metadata reads into shared, bounded cache blocks.

    Large column reads stay single ranges. This avoids one HTTPS round trip per
    tiny Parquet dictionary/page while never prefetching whole image columns.
    """
    def __init__(self,source,block_bytes=65536):
        self.source=source;self.position=0;self.block_bytes=block_bytes
        self.prefetched=[]
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        position=offset+(self.position if whence==1 else self.source.size if whence==2 else 0)
        if whence not in (0,1,2) or position<0:raise ValueError('Invalid buffered seek')
        self.position=position;return position
    def prefetch(self, ranges, max_bytes=32_000_000):
        """Pin one row group's selected column chunks, never arbitrary gaps."""
        self.prefetched=[]
        if sum(end-start for start,end in ranges)>max_bytes:return
        for start,end in ranges:
            if not 0<=start<end<=self.source.size:raise ValueError('Invalid metadata prefetch range')
            self.source.seek(start)
            self.prefetched.append((start,self.source.read(end-start)))

    def read(self,size=-1):
        count=max(0,self.source.size-self.position) if size<0 else min(size,max(0,self.source.size-self.position))
        if not count:return b''
        for start,data in self.prefetched:
            if start<=self.position and self.position+count<=start+len(data):
                result=data[self.position-start:self.position-start+count];self.position+=len(result);return result
        if count>=self.block_bytes:
            self.source.seek(self.position);data=self.source.read(count);self.position+=len(data);return data
        parts=[];remaining=count
        while remaining:
            start=self.position//self.block_bytes*self.block_bytes
            self.source.seek(start);block=self.source.read(min(self.block_bytes,self.source.size-start))
            begin=self.position-start;data=block[begin:begin+remaining]
            if not data:raise ValueError('Buffered range read made no progress')
            parts.append(data);remaining-=len(data);self.position+=len(data)
        return b''.join(parts)
    def readinto(self,buffer):
        data=self.read(len(buffer));buffer[:len(data)]=data;return len(data)
