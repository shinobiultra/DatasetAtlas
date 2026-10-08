import io
from urllib.parse import urlsplit

import pytest

from dataset_atlas.storage.ranges import HttpsRangeReader,range_fingerprint


def transport(monkeypatch,status=206):
    calls=[]
    class Response(io.BytesIO):
        def __init__(self,host):
            super().__init__(b'x');self.status=302 if host=='huggingface.co' else status;self.will_close=True
        def getheader(self,key,default=None):
            return {'Location':'https://cdn.example.org/file','ETag':'"native"',
                    'Content-Length':'1','Content-Range':'bytes 0-0/9'}.get(key,default)
    class Connection:
        def __init__(self,host,*args):self.host=host
        def request(self,method,target,headers):calls.append((self.host,method,dict(headers)))
        def getresponse(self):return Response(self.host)
        def close(self):pass
    monkeypatch.setattr('dataset_atlas.storage.ranges._PinnedHTTPSConnection',Connection)
    monkeypatch.setattr('dataset_atlas.storage.https.HttpsFetcher._destination',
        lambda self,url:(urlsplit(url).hostname,443,'93.184.216.34','/file'))
    monkeypatch.setenv('HF_TOKEN','hf_fixture_only')
    return calls


def test_range_credentials_stay_on_hub_and_refresh_per_request(monkeypatch):
    calls=transport(monkeypatch)
    with HttpsRangeReader('https://huggingface.co/file',size=9,etag='"native"',
            allowed_hosts=['huggingface.co','cdn.example.org'],byte_budget=1,credential_profile='huggingface') as source:
        assert source.read(1)==b'x'
    assert calls[0][2]['Authorization']=='Bearer hf_fixture_only'
    assert 'Authorization' not in calls[1][2]


def test_get_signed_fingerprint_checks_single_byte_bounds_and_strips_credentials(monkeypatch):
    calls=transport(monkeypatch)
    assert range_fingerprint('https://huggingface.co/file',expected_size=9,
        allowed_hosts=['huggingface.co','cdn.example.org'],credential_profile='huggingface',probe_method='GET')=='"native"'
    assert all(call[1]=='GET' and call[2]['Range']=='bytes=0-0' for call in calls)
    assert 'Authorization' in calls[0][2] and 'Authorization' not in calls[1][2]


def test_get_fingerprint_never_consumes_an_ignored_range(monkeypatch):
    transport(monkeypatch,status=200)
    with pytest.raises(ValueError,match='requires HTTP 206'):
        range_fingerprint('https://huggingface.co/file',expected_size=9,
            allowed_hosts=['huggingface.co','cdn.example.org'],probe_method='GET')
