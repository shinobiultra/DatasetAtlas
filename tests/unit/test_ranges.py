import io
import zipfile
import pytest
from dataset_atlas.storage.ranges import HttpsRangeReader
from dataset_atlas.storage.cache import BoundedCache


def transport(monkeypatch,payload,*,status=206,etag='"v1"',wrong_bounds=False):
    calls=[]
    class Connection:
        def __init__(self,*args):pass
        def request(self,method,target,headers):
            self.start,self.end=map(int,headers['Range'][6:].split('-'));calls.append((self.start,self.end))
            assert headers['If-Match']=='"v1"'
        def getresponse(self):
            response=io.BytesIO(payload[self.start:self.end+1]);response.status=status
            headers={'ETag':etag,'Content-Range':f'bytes {self.start}-{self.end}/{len(payload)+(1 if wrong_bounds else 0)}','Content-Length':str(self.end-self.start+1)}
            response.getheader=lambda name,default=None:headers.get(name,default)
            return response
        def close(self):pass
    monkeypatch.setattr('dataset_atlas.storage.ranges._PinnedHTTPSConnection',Connection)
    monkeypatch.setattr('dataset_atlas.storage.https.HttpsFetcher._destination',lambda self,url:('example.org',443,'1.1.1.1','/source'))
    return calls


def reader(payload,**kwargs):return HttpsRangeReader('https://example.org/source',size=len(payload),etag='"v1"',allowed_hosts=['example.org'],byte_budget=100_000,**kwargs)


def test_zip_random_access_and_cached_exact_bytes(tmp_path,monkeypatch):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('first.jpg',b'original image');z.writestr('unrequested.bin',b'x'*1_000_000)
    data=stream.getvalue();calls=transport(monkeypatch,data)
    cache=BoundedCache(tmp_path/'cache',100_000)
    with reader(data,cache=cache) as source,zipfile.ZipFile(source) as z:
        assert z.read('first.jpg')==b'original image'
        assert source.bytes_fetched<1000
    initial=len(calls)
    with reader(data,cache=cache) as source,zipfile.ZipFile(source) as z:assert z.read('first.jpg')==b'original image'
    assert len(calls)==initial


def test_small_zip_header_and_payload_reads_share_bounded_range_blocks(tmp_path, monkeypatch):
    from dataset_atlas.storage.ranges import SmallReadBuffer
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        z.writestr('image.png', b'original image bytes')
        z.writestr('unrequested.bin', b'x' * 1_000_000)
    payload = stream.getvalue()
    calls = transport(monkeypatch, payload)
    cache = BoundedCache(tmp_path/'cache', 200_000)
    source = HttpsRangeReader('https://example.org/source', size=len(payload), etag='"v1"',
                             allowed_hosts=['example.org'], byte_budget=131072, cache=cache)
    with source, zipfile.ZipFile(SmallReadBuffer(source)) as z:
        assert z.read('image.png') == b'original image bytes'
        assert source.bytes_fetched <= 131072
    assert len(calls) == 2  # One tail block and one image block; no full ZIP copy.


@pytest.mark.parametrize('kwargs,message',[({'status':200},'HTTP 206'),({'etag':'"v2"'},'ETag changed'),({'wrong_bounds':True},'bounds')])
def test_range_source_drift_and_ignored_range_fail(monkeypatch,kwargs,message):
    transport(monkeypatch,b'0123456789',**kwargs)
    with pytest.raises(ValueError,match=message):reader(b'0123456789').read(4)


def test_range_bounds_and_budget(monkeypatch):
    transport(monkeypatch,b'0123456789')
    r=HttpsRangeReader('https://example.org/source',size=10,etag='"v1"',allowed_hosts=['example.org'],byte_budget=4)
    assert r.read(3)==b'012'
    with pytest.raises(ValueError,match='budget'):r.read(2)
    with pytest.raises(ValueError):r.seek(-1)
    with pytest.raises(ValueError):HttpsRangeReader('https://example.org/source',size=10,etag='W/"v1"',allowed_hosts=['example.org'],byte_budget=4)


def test_keepalive_reuses_validated_origin_and_recovers_stale_socket_once(monkeypatch):
    import http.client
    instances=[];destinations=[]
    class Connection:
        def __init__(self,*args):self.calls=0;self.closed=False;instances.append(self)
        def request(self,method,target,headers):
            self.calls+=1
            if len(instances)==1 and self.calls==3:raise http.client.RemoteDisconnected('stale')
            self.start,self.end=map(int,headers['Range'][6:].split('-'))
        def getresponse(self):
            body=io.BytesIO(b'0123456789'[self.start:self.end+1]);body.status=206;body.will_close=False
            headers={'ETag':'"v1"','Content-Range':f'bytes {self.start}-{self.end}/10','Content-Length':str(self.end-self.start+1)}
            body.getheader=lambda key,default=None:headers.get(key,default)
            return body
        def close(self):self.closed=True
    def destination(self,url):
        destinations.append(url);return 'example.org',443,'1.1.1.1','/source'
    monkeypatch.setattr('dataset_atlas.storage.ranges._PinnedHTTPSConnection',Connection)
    monkeypatch.setattr('dataset_atlas.storage.https.HttpsFetcher._destination',destination)
    with reader(b'0123456789') as source:
        assert source.read(2)==b'01' and source.read(2)==b'23'
        assert len(instances)==1 and len(destinations)==2
        assert source.read(2)==b'45' and len(instances)==2
        assert source.bytes_fetched==6
    assert all(connection.closed for connection in instances)


def test_small_read_buffer_reuses_aligned_ranges_and_keeps_large_reads_single():
    import io
    from dataset_atlas.storage.ranges import SmallReadBuffer
    class Source(io.BytesIO):
        def __init__(self):super().__init__(bytes(range(256))*100);self.size=25600;self.reads=[]
        def read(self,n=-1):self.reads.append((self.tell(),n));return super().read(n)
    source=Source();buffer=SmallReadBuffer(source,1024)
    buffer.seek(40);assert buffer.read(3)==bytes([40,41,42])
    buffer.seek(80);assert buffer.read(3)==bytes([80,81,82])
    # Underlying HTTPS cache keys are identical for neighbours.
    assert source.reads[:2]==[(0,1024),(0,1024)]
    buffer.seek(100);assert len(buffer.read(5000))==5000
    assert source.reads[-1]==(100,5000)


def test_redirect_is_reused_but_every_destination_is_revalidated(monkeypatch):
    destinations=[];requests=[]
    def destination(self,url):
        destinations.append(url)
        return ('example.org',443,'1.1.1.1','/signed' if url.endswith('/signed') else '/original')
    class Connection:
        def __init__(self,*args):pass
        def request(self,method,target,headers):self.target=target;self.headers=headers;requests.append(target)
        def getresponse(self):
            start,end=map(int,self.headers['Range'][6:].split('-'))
            body=io.BytesIO(b'0123456789'[start:end+1] if self.target=='/signed' else b'')
            body.status=206 if self.target=='/signed' else 302
            headers={'Location':'https://example.org/signed','ETag':'"v1"','Content-Range':f'bytes {start}-{end}/10','Content-Length':str(end-start+1)}
            body.getheader=lambda key,default=None:headers.get(key,default)
            return body
        def close(self):pass
    monkeypatch.setattr('dataset_atlas.storage.ranges._PinnedHTTPSConnection',Connection)
    monkeypatch.setattr('dataset_atlas.storage.https.HttpsFetcher._destination',destination)
    with reader(b'0123456789') as source:
        assert source.read(2)==b'01'
        assert source.read(2)==b'23'
    assert requests==['/original','/signed','/signed']
    assert len(destinations)==3


def flaky_transport(monkeypatch, payload, failures, status=503):
    """Fail the first `failures` requests with a throttling status, then serve normally."""
    calls = {'n': 0}
    class Connection:
        def __init__(self, *args): pass
        def request(self, method, target, headers):
            self.start, self.end = map(int, headers['Range'][6:].split('-')); calls['n'] += 1
        def getresponse(self):
            response = io.BytesIO(b'' if calls['n'] <= failures else payload[self.start:self.end + 1])
            response.status = status if calls['n'] <= failures else 206
            headers = {'ETag': '"v1"', 'Content-Range': f'bytes {self.start}-{self.end}/{len(payload)}', 'Content-Length': str(self.end - self.start + 1)}
            response.getheader = lambda name, default=None: headers.get(name, default)
            return response
        def close(self): pass
    monkeypatch.setattr('dataset_atlas.storage.ranges._PinnedHTTPSConnection', Connection)
    monkeypatch.setattr('dataset_atlas.storage.https.HttpsFetcher._destination', lambda self, url: ('example.org', 443, '1.1.1.1', '/source'))
    slept = []
    monkeypatch.setattr('dataset_atlas.storage.ranges.time.sleep', slept.append)
    return calls, slept


@pytest.mark.parametrize('status', [429, 502, 503, 504])
def test_throttling_is_retried_with_backoff_and_does_not_count_against_the_budget(monkeypatch, status):
    payload = bytes(range(256)) * 4
    calls, slept = flaky_transport(monkeypatch, payload, failures=2, status=status)
    with reader(payload) as source:
        assert source.read(100) == payload[:100]
        assert source.bytes_fetched == 100
    assert calls['n'] == 3 and slept == [1, 2]


def test_persistent_unavailability_gives_up_with_a_clear_error(monkeypatch):
    payload = b'x' * 1000
    calls, slept = flaky_transport(monkeypatch, payload, failures=99)
    with reader(payload) as source, pytest.raises(ValueError, match='unavailable: HTTP 503 after 4 retries'):
        source.read(10)
    assert calls['n'] == 5 and slept == [1, 2, 4, 8]


def test_integrity_failures_are_never_retried(monkeypatch):
    payload = b'x' * 1000
    calls = transport(monkeypatch, payload, etag='"changed"')
    with reader(payload) as source, pytest.raises(ValueError, match='ETag changed'):
        source.read(10)
    assert len(calls) == 1
