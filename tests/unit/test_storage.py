from __future__ import annotations

import os
import socket

import pytest

from dataset_atlas.storage import BoundedCache, CacheIdentity, HttpsFetcher, SafeRoots, read_rooted_file


def test_roots_reject_traversal_and_symlinks(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "safe.txt").write_text("safe")
    (tmp_path / "secret.txt").write_text("secret")
    (root / "escape").symlink_to(tmp_path / "secret.txt")
    roots = SafeRoots({"data": root})
    with roots.open("data", "safe.txt") as stream:
        assert stream.read() == b"safe"
    for path in ("../secret.txt", "/etc/passwd", "escape", "x/../../secret.txt", "a\\..\\secret.txt"):
        with pytest.raises((ValueError, OSError, FileNotFoundError)):
            roots.open("data", path)
        with pytest.raises((ValueError, OSError, FileNotFoundError)):
            roots.resolve("data", path)
    assert read_rooted_file(root / "safe.txt", [root], 4) == b"safe"
    with pytest.raises(ValueError, match="bound"):
        read_rooted_file(root / "safe.txt", [root], 3)
    with pytest.raises((ValueError, OSError)):
        read_rooted_file(root / "escape", [root], 100)
    link_dir = root / "linked"
    link_dir.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        read_rooted_file(link_dir / "secret.txt", [root], 100)


def test_cache_revision_pinning_and_bound(tmp_path):
    cache = BoundedCache(tmp_path / "cache", max_bytes=6)
    original = CacheIdentity("revision-1", "asset", "original")
    preview = CacheIdentity("revision-1", "asset", "preview", "resize-1")
    changed = CacheIdentity("revision-2", "asset", "original")
    for identity, data in ((original, b"abc"), (preview, b"def")):
        partial = cache.partial_path(identity)
        partial.write_bytes(data)
        cache.commit(identity, partial)
    cache.pin(original)
    partial = cache.partial_path(changed)
    partial.write_bytes(b"ghi")
    cache.commit(changed, partial)
    assert cache.get(original).read_bytes() == b"abc"
    assert cache.get(preview) is None
    assert cache.get(changed).read_bytes() == b"ghi"
    assert cache.usage()["bytes"] == 6
    with pytest.raises(ValueError, match="Pinned"):
        cache.evict(original)


def test_rooted_read_rejects_file_swapped_to_symlink(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    safe = root / "safe.txt"
    safe.write_bytes(b"approved")
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"secret")
    import dataset_atlas.storage.local as module
    real_open = os.open
    def swap_before_open(path, flags, *args, **kwargs):
        if path == "safe.txt":
            safe.unlink()
            safe.symlink_to(secret)
        return real_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(module.os, "open", swap_before_open)
    with pytest.raises(ValueError, match="configured root"):
        read_rooted_file(safe, [root], 100)


def test_https_rejects_private_dns_and_redirect(monkeypatch, tmp_path):
    fetcher = HttpsFetcher({"example.org"})
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="nonpublic"):
        fetcher._destination("https://example.org/data")

    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.215.14", 443))])
    class Response:
        status = 302
        def getheader(self, name, default=None):
            return "https://127.0.0.1/private" if name == "Location" else default
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Response()
        def close(self): pass
    import dataset_atlas.storage.https as module
    monkeypatch.setattr(module, "_PinnedHTTPSConnection", Connection)
    cache = BoundedCache(tmp_path / "cache", max_bytes=1024)
    with pytest.raises(ValueError, match="allowlisted"):
        fetcher.fetch("https://example.org/data", cache, CacheIdentity("r", "a", "original"))


def test_https_prefers_public_ipv4_when_ipv6_route_may_be_absent(monkeypatch):
    fetcher = HttpsFetcher({"example.org"})
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.215.14", 443)),
    ])
    assert fetcher._destination("https://example.org/data")[2] == "93.184.215.14"
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET6, socket.SOCK_STREAM, 0, "", ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(ValueError, match="nonpublic"):
        fetcher._destination("https://example.org/data")


def test_https_interrupted_transfer_resumes_only_with_matching_range(monkeypatch, tmp_path):
    import dataset_atlas.storage.https as module
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.215.14", 443))])
    responses = [
        (200, {"Content-Length": "6", "ETag": '"revision-1"'}, b"abc"),
        (206, {"Content-Length": "3", "Content-Range": "bytes 3-5/6", "ETag": '"revision-1"'}, b"def"),
    ]
    requests = []
    class Response:
        def __init__(self, status, headers, body):
            self.status, self.headers, self.body = status, headers, body
        def getheader(self, name, default=None): return self.headers.get(name, default)
        def read(self, amount):
            chunk, self.body = self.body[:amount], self.body[amount:]
            return chunk
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, method, target, headers): requests.append(headers)
        def getresponse(self): return Response(*responses.pop(0))
        def close(self): pass
    monkeypatch.setattr(module, "_PinnedHTTPSConnection", Connection)
    fetcher = HttpsFetcher({"example.org"}, max_bytes=10)
    cache = BoundedCache(tmp_path / "cache", max_bytes=10)
    identity = CacheIdentity("revision-1", "asset", "original")
    with pytest.raises(ValueError, match="ended before Content-Length"):
        fetcher.fetch("https://example.org/data", cache, identity)
    assert cache.partial_path(identity).read_bytes() == b"abc"
    result = fetcher.fetch("https://example.org/data", cache, identity)
    assert result.read_bytes() == b"abcdef"
    assert requests[1]["Range"] == "bytes=3-"
    assert requests[1]["If-Range"] == '"revision-1"'


def test_huggingface_credentials_are_local_and_not_forwarded_to_cdn(monkeypatch, tmp_path):
    import dataset_atlas.storage.https as module
    from dataset_atlas.storage.auth import source_headers
    monkeypatch.delenv('HF_TOKEN', raising=False)
    monkeypatch.setenv('HF_HOME', str(tmp_path/'hf'))
    monkeypatch.setenv('HF_TOKEN_PATH', str(tmp_path/'hf'/'token'))
    with pytest.raises(ValueError, match='missing'):
        source_headers('huggingface', 'huggingface.co')
    monkeypatch.setenv('HF_TOKEN', 'hf_fixture_secret')
    assert source_headers('huggingface', 'cdn.huggingface.co') == {}
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.215.14', 443))])
    requests = []
    class Response:
        def __init__(self, redirected):
            self.status = 200 if redirected else 302
            self.body = b'abc'
        def getheader(self, name, default=None):
            return {'Location': 'https://us.aws.cdn.hf.co/image', 'Content-Length': '3'}.get(name, default)
        def read(self, size):
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk
    class Connection:
        def __init__(self, host, *a, **k): self.host = host
        def request(self, method, target, headers): requests.append((self.host, dict(headers)))
        def getresponse(self): return Response(self.host != 'huggingface.co')
        def close(self): pass
    monkeypatch.setattr(module, '_PinnedHTTPSConnection', Connection)
    cache = BoundedCache(tmp_path/'cache', max_bytes=100)
    result = HttpsFetcher({'huggingface.co', 'us.aws.cdn.hf.co'}, credential_profile='huggingface').fetch(
        'https://huggingface.co/datasets/fixture/image', cache, CacheIdentity('r', 'a', 'original'))
    assert result.read_bytes() == b'abc'
    assert requests[0][1]['Authorization'] == 'Bearer hf_fixture_secret'
    assert 'Authorization' not in requests[1][1]
    assert all(b'hf_fixture_secret' not in path.read_bytes() for path in (tmp_path/'cache').rglob('*') if path.is_file())
