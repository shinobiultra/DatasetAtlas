"""Four bounded connections for large sequential reads of one pinned source."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import io

from .ranges import HttpsRangeReader


class ParallelRangeReader(io.RawIOBase):
    """Return disjoint pinned ranges in source order, with one aggregate byte cap."""
    def __init__(self,url,*,size,etag,allowed_hosts,byte_budget,cache=None,cancel=None,reader_factory=HttpsRangeReader,connections=4):
        super().__init__()
        if type(byte_budget) is not int or byte_budget<1:raise ValueError('A positive aggregate transfer budget is required')
        if type(connections) is not int or not 1<=connections<=8:raise ValueError('Native source connections must be within1..8')
        self.size=size;self.position=0;self.budget=byte_budget;self.reserved=0
        self.readers=[reader_factory(url,size=size,etag=etag,allowed_hosts=allowed_hosts,byte_budget=byte_budget,
            cache=cache,cancel=cancel) for _ in range(connections)]
        self.pool=ThreadPoolExecutor(max_workers=connections,thread_name_prefix='atlas-native-range')
    @property
    def bytes_fetched(self):return sum(reader.bytes_fetched for reader in self.readers)
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        value=offset+(self.position if whence==1 else self.size if whence==2 else 0)
        if whence not in (0,1,2) or value<0:raise ValueError('Invalid native source seek')
        self.position=value;return value
    def read(self,size=-1):
        if self.closed:raise ValueError('Native source reader is closed')
        count=min(size,max(0,self.size-self.position)) if size>=0 else max(0,self.size-self.position)
        if not count:return b''
        if count>32_000_000 or self.reserved+count>self.budget:raise ValueError('Native source read exceeds aggregate byte budget')
        # Reserve before dispatch, including failed/partial requests. Cache hits
        # may make actual transfer smaller; a failed request never restores credit.
        self.reserved+=count
        def fetch(reader,start,length):
            reader.seek(start);data=reader.read(length)
            if len(data)!=length:raise ValueError('Native source range is truncated')
            return data
        if count<4<<20:
            data=fetch(self.readers[0],self.position,count)
        else:
            parts=[];start=self.position;chunk=(count+len(self.readers)-1)//len(self.readers)
            for reader in self.readers:
                length=min(chunk,self.position+count-start)
                if length:parts.append(self.pool.submit(fetch,reader,start,length));start+=length
            data=b''.join(future.result() for future in parts)
        self.position+=len(data);return data
    def readinto(self,buffer):
        data=self.read(len(buffer));buffer[:len(data)]=data;return len(data)
    def close(self):
        if not self.closed:
            self.pool.shutdown(wait=True,cancel_futures=True)
            for reader in self.readers:reader.close()
        super().close()
