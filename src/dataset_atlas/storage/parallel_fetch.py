"""Bounded parallel acquisition admitted only by a complete publisher checksum.

Unverified ranges stay in an Atlas cache partial. They are never served as
originals, and a resumed prefix is admitted only after the entire assembled
file passes its pinned checksum. No ETag is inferred from a publisher MD5.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import threading
import time
from typing import Any
from urllib.parse import urljoin

from .https import HttpsFetcher,_PinnedHTTPSConnection


def fetch_checksum_ranges(entry,cache,identity,*,allowed_hosts,byte_budget,check=lambda:None,progress=lambda n:None,
                          workers=4,chunk_bytes=16<<20):
    from dataset_atlas.preparation import atomic
    size=entry['bytes'];url=entry['url'];checksum=entry.get('sha256') or entry.get('md5')
    algorithm='sha256' if entry.get('sha256') else 'md5'
    if not checksum or type(size) is not int or not 1<=size<=byte_budget or not 1<=workers<=4 or not 1<=chunk_bytes<=32<<20:
        raise ValueError('Parallel acquisition requires a full publisher checksum and explicit limits')
    cached=cache.get(identity)
    if cached:return cached,{'network_bytes':0,'reused_complete_bytes':size,'reused_prefix_bytes':0}
    partial=cache.partial_path(identity);checkpoint=partial.with_suffix('.ranges.json')
    source={'url':url,'bytes':size,'checksum':checksum,'algorithm':algorithm,'chunk_bytes':chunk_bytes}
    state: dict[str,Any]
    if checkpoint.exists():
        state=json.loads(checkpoint.read_text())
        if state['source']!=source or not partial.is_file():raise ValueError('Partial acquisition checkpoint changed')
    else:
        prior=partial.with_suffix('.json')
        prefix=0
        if partial.exists():
            metadata=json.loads(prior.read_text()) if prior.exists() else {}
            if metadata.get('url')!=url or metadata.get('total_bytes')!=size:raise ValueError('Partial prefix lacks matching native source metadata')
            prefix=partial.stat().st_size
            if not 0<=prefix<=size:raise ValueError('Partial prefix exceeds complete source')
        else:partial.touch()
        state={'source':source,'prefix_bytes':prefix,'completed':[],'network_bytes':prefix}
        atomic(checkpoint,state)
    prefix=state['prefix_bytes'];completed=set(state['completed']);network=state['network_bytes'];initial_network=network
    if type(prefix) is not int or not 0<=prefix<=size or type(network) is not int or not prefix<=network<=byte_budget:
        raise ValueError('Invalid native partial checkpoint byte counts')
    lock=threading.Lock();stop=threading.Event();reserved=0
    fetcher=HttpsFetcher(allowed_hosts,max_bytes=size,timeout=60)
    def cancel():
        if stop.is_set():raise InterruptedError('Parallel acquisition interrupted')
        check()
    def save():
        state.update(completed=sorted(completed),network_bytes=network)
        atomic(checkpoint,state)
    def charge(count):
        nonlocal network,reserved
        with lock:
            network+=count;reserved-=count
            if network>byte_budget:raise ValueError('Parallel acquisition exceeds transfer budget')
            progress(network)
    def read_range(start,end):
        nonlocal reserved
        count=end-start+1
        with lock:
            if network+reserved+count>byte_budget:raise ValueError('Parallel acquisition has insufficient remaining transfer budget')
            reserved+=count
        current=url;consumed=0
        try:
            for hop in range(fetcher.max_redirects+1):
                cancel();host,port,address,target=fetcher._destination(current)
                connection=_PinnedHTTPSConnection(host,address,port,fetcher.timeout)
                try:
                    response=None
                    for attempt in range(4):
                        connection.request('GET',target,headers={'Accept-Encoding':'identity','Range':f'bytes={start}-{end}','User-Agent':'DatasetAtlas/0.2'})
                        response=connection.getresponse()
                        if response.status not in (429,502,503,504):break
                        connection.close()
                        if attempt==3:raise ValueError(f'Native source range failed after four attempts: HTTP {response.status}')
                        for _ in range(10*(attempt+1)):cancel();time.sleep(.1)
                        connection=_PinnedHTTPSConnection(host,address,port,fetcher.timeout)
                    if response is None:raise ValueError('Native source has no response')
                    if response.status in (301,302,303,307,308):
                        location=response.getheader('Location')
                        if not location:raise ValueError('Native range redirect lacks location')
                        current=urljoin(current,location);continue
                    if response.status!=206:raise ValueError(f'Native acquisition requires HTTP 206; received {response.status}')
                    if response.getheader('Content-Encoding','identity')!='identity':raise ValueError('Encoded native ranges are unsupported')
                    if response.getheader('Content-Range')!=f'bytes {start}-{end}/{size}' or response.getheader('Content-Length')!=str(count):
                        raise ValueError('Native range bounds or length changed')
                    data=bytearray()
                    while len(data)<count:
                        cancel();block=response.read(min(1<<20,count-len(data)))
                        if not block:raise ValueError('Native range ended before its declared length')
                        consumed+=len(block);charge(len(block));data.extend(block)
                    return data
                finally:connection.close()
            raise ValueError('Too many native range redirects')
        finally:
            with lock:reserved-=count-consumed
    def transfer(item):
        ordinal,start,end=item
        if ordinal in completed:return
        data=read_range(start,end)
        # Separate handles allow concurrent writes at disjoint pinned offsets.
        with partial.open('r+b') as stream:stream.seek(start);stream.write(data);stream.flush()
        with lock:completed.add(ordinal);save()
    ranges=[(i,start,min(size-1,start+chunk_bytes-1)) for i,start in enumerate(range(prefix,size,chunk_bytes))]
    if any(i<0 or i>=len(ranges) for i in completed):raise ValueError('Native checkpoint contains invalid completed ranges')
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(transfer,item) for item in ranges if item[0] not in completed]
            try:
                for future in as_completed(futures):future.result()
            except BaseException:stop.set();raise
        cancel()
        if partial.stat().st_size!=size:raise ValueError('Complete native acquisition length changed')
        with partial.open('rb') as stream:actual=hashlib.file_digest(stream,algorithm).hexdigest()
        if actual!=checksum:raise ValueError('Complete native acquisition differs from publisher checksum')
        with partial.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
        target=cache.commit(identity,partial,expected_sha256=sha,fingerprint_type='sha256',fingerprint=sha)
        checkpoint.unlink();partial.with_suffix('.json').unlink(missing_ok=True)
        return target,{'network_bytes':network,'network_bytes_this_attempt':network-initial_network,
                       'reused_prefix_bytes':prefix,'publisher_checksum_algorithm':algorithm,'publisher_checksum_verified':actual}
    finally:
        if partial.exists():
            with lock:save()
