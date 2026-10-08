"""The two official SVHN files: public HTTP bytes admitted only by pinned SHA-256.

This exception is unavailable to media, providers, tools, and arbitrary recipes.
No bytes enter an adapter until the full published file matches its checksum.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import socket

from .https import HttpsFetcher

SVHN_FILES = {
    'http://ufldl.stanford.edu/housenumbers/train_32x32.mat': (182040794,'435e94d69a87fde4fd4d7f3dd208dfc32cb6ae8af2240d066de1df7508d083b8'),
    'http://ufldl.stanford.edu/housenumbers/test_32x32.mat': (64275384,'cdce80dfb2a2c4c6160906d0bd7c68ec5a99d7ca4831afa54f09182025b6a75b'),
}


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self,host,address):
        super().__init__(host,port=80,timeout=30)
        self.address=address

    def connect(self):
        self.sock=socket.create_connection((self.address,self.port),self.timeout)


def fetch_svhn(entry,cache,identity,*,cancel=lambda:None,progress=lambda count:None):
    url=entry['url']
    expected=SVHN_FILES.get(url)
    if expected is None or expected!=(entry.get('bytes'),entry.get('sha256')):
        raise ValueError('HTTP acquisition is restricted to the two checksum-pinned official SVHN files')
    length,checksum=expected
    cached=cache.get(identity)
    if cached:
        with cached.open('rb') as stream:
            if cached.stat().st_size!=length or hashlib.file_digest(stream,'sha256').hexdigest()!=checksum:
                raise ValueError('Cached SVHN bytes differ from pinned source')
        return cached
    if length>cache.max_bytes:raise ValueError('SVHN file exceeds the admitted cache budget')
    host='ufldl.stanford.edu'
    addresses={result[4][0] for result in HttpsFetcher._resolve(host,80)}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('SVHN destination resolved to a nonpublic address')
    ipv4=sorted(address for address in addresses if ipaddress.ip_address(address).version==4)
    connection=_PinnedHTTPConnection(host,(ipv4 or sorted(addresses))[0])
    partial=cache.partial_path(identity)
    try:
        connection.request('GET',url.removeprefix('http://'+host),headers={'Accept-Encoding':'identity','User-Agent':'DatasetAtlas/0.2'})
        response=connection.getresponse()
        if response.status!=200 or response.getheader('Content-Encoding') not in {None,'identity'}:
            raise ValueError(f'Official SVHN HTTP source refused: status {response.status}; redirects are not followed')
        size=response.getheader('Content-Length')
        if size is not None and size!=str(length):raise ValueError('Official SVHN length changed')
        count=0;digest=hashlib.sha256()
        with partial.open('wb') as out:
            while True:
                cancel()
                chunk=response.read(min(1<<20,length-count+1))
                if not chunk:break
                count+=len(chunk)
                if count>length:raise ValueError('SVHN transfer exceeds pinned byte budget')
                digest.update(chunk);out.write(chunk);progress(count)
        if count!=length or digest.hexdigest()!=checksum:raise ValueError('Official SVHN bytes differ from pinned SHA-256')
        return cache.commit(identity,partial,expected_sha256=checksum,fingerprint_type='sha256',fingerprint=checksum)
    finally:
        connection.close()
        partial.unlink(missing_ok=True)
