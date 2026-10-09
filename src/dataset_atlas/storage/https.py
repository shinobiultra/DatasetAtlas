"""HTTPS-only bounded fetch with DNS/IP pinning on every redirect hop."""
from __future__ import annotations

import http.client
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

from .cache import BoundedCache, CacheIdentity


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname: str, address: str, port: int, timeout: float):
        super().__init__(hostname, port=port, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        self.sock = socket.create_connection((self.address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class HttpsFetcher:
    def __init__(self, allowed_hosts: set[str] | list[str], *, timeout: float = 20,
                 max_redirects: int = 4, max_bytes: int = 64 * 1024 * 1024, credential_profile: str | None = None):
        self.allowed_hosts = {host.lower().rstrip(".") for host in allowed_hosts}
        # An entry like "*.example.com" admits subdomains of example.com (never example.com itself, never other
        # domains). Some CDNs redirect to a fresh random subdomain per request; the wildcard must be opted into.
        if any("*" in host and not (host.startswith("*.") and len(host) > 3 and "*" not in host[2:]) for host in self.allowed_hosts):
            raise ValueError("Host patterns may only use a leading wildcard label, as in *.example.com")
        self.allowed_suffixes = tuple(host[1:] for host in self.allowed_hosts if host.startswith("*.") and len(host) > 3 and "*" not in host[2:])
        self.allowed_hosts = {host for host in self.allowed_hosts if not host.startswith("*.")}
        if not (self.allowed_hosts or self.allowed_suffixes) or max_bytes <= 0 or max_redirects < 0:
            raise ValueError("Allowlisted hosts and positive fetch limits are required")
        if credential_profile not in {None,"huggingface"}:raise ValueError("Unknown source credential profile")
        self.credential_profile = credential_profile
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.max_bytes = max_bytes
        self.bytes_fetched = 0

    @staticmethod
    def _resolve(host: str, port: int):
        """A resolver that briefly fails is retried; a host that never resolves ends with an error that names it."""
        for attempt in range(5):
            try:
                return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            except socket.gaierror as error:
                if attempt == 4:
                    raise ValueError(f"Host did not resolve after {attempt} retries: {host} ({error.strerror})") from None
                time.sleep(min(8, 2 ** attempt))

    def _destination(self, url: str) -> tuple[str, int, str, str]:
        parsed = urlsplit(url)
        if parsed.scheme.lower() != "https" or parsed.username or parsed.password or not parsed.hostname:
            raise ValueError("Only credential-free HTTPS URLs are allowed")
        host = parsed.hostname.lower().rstrip(".")
        if host not in self.allowed_hosts and not any(host.endswith(suffix) for suffix in self.allowed_suffixes):
            raise ValueError("HTTPS destination is not allowlisted")
        port = parsed.port or 443
        if port != 443:
            raise ValueError("Only HTTPS port 443 is allowed")
        addresses = {entry[4][0] for entry in self._resolve(host, port)}
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError("HTTPS destination resolved to a nonpublic address")
        target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        # Some hosts publish both address families on machines without an IPv6
        # route. Retain the all-address public-IP check above, then choose a
        # deterministic reachable IPv4 candidate when one is available.
        ipv4 = sorted(address for address in addresses
                      if ipaddress.ip_address(address).version == 4)
        return host, port, (ipv4 or sorted(addresses))[0], target

    def fetch(self, url: str, cache: BoundedCache, identity: CacheIdentity,
              *, expected_sha256: str | None = None, byte_budget: int | None = None, cancel=None, progress=None) -> Path:
        cached = cache.get(identity)
        if cached:
            return cached
        limit = min(self.max_bytes, cache.max_bytes, byte_budget if byte_budget is not None else self.max_bytes)
        if limit <= 0:
            raise ValueError("A positive byte budget is required")
        partial = cache.partial_path(identity)
        metadata_path = partial.with_suffix(".json")
        metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
        if metadata.get("url") != url:
            partial.unlink(missing_ok=True)
            metadata = {}
        offset = partial.stat().st_size if partial.exists() else 0
        if offset and (not metadata.get("strong_etag") or offset > limit):
            partial.unlink(missing_ok=True)
            offset = 0
        current = url
        for hop in range(self.max_redirects + 1):
            host, port, address, target = self._destination(current)
            connection = _PinnedHTTPSConnection(host, address, port, self.timeout)
            headers = {"Accept-Encoding": "identity", "User-Agent": "DatasetAtlas/0.1"}
            from .auth import source_headers
            headers.update(source_headers(self.credential_profile,host))
            if offset:
                headers["Range"] = f"bytes={offset}-"
                headers["If-Range"] = metadata["strong_etag"]
            try:
                connection.request("GET", target, headers=headers)
                response = connection.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader("Location")
                    if not location:
                        raise ValueError("Redirect without Location")
                    current = urljoin(current, location)
                    # Validate before opening another connection, including host and DNS.
                    self._destination(current)
                    continue
                if response.status not in (200, 206):
                    raise ValueError(f"HTTPS fetch failed: HTTP {response.status}")
                range_end = None
                total_size = None
                if response.status == 206:
                    range_value = response.getheader("Content-Range", "")
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", range_value)
                    if not offset or not match or int(match.group(1)) != offset:
                        raise ValueError("Unexpected Content-Range on resumed transfer")
                    range_end, total_size = int(match.group(2)), int(match.group(3))
                    if range_end < offset or range_end >= total_size or total_size > limit:
                        raise ValueError("Invalid or over-budget Content-Range")
                    if metadata.get("total_bytes") is not None and total_size != metadata["total_bytes"]:
                        raise ValueError("Source length changed during resumed transfer")
                    if response.getheader("ETag") != metadata.get("strong_etag"):
                        raise ValueError("ETag changed during resumed transfer")
                else:
                    offset = 0
                    partial.unlink(missing_ok=True)
                length = response.getheader("Content-Length")
                if length is not None:
                    length = int(length)
                    if length < 0 or offset + length > limit:
                        raise ValueError("Content-Length exceeds fetch budget")
                    if range_end is not None and length != range_end - offset + 1:
                        raise ValueError("Content-Length disagrees with Content-Range")
                if response.status == 200:
                    total_size = length
                etag = response.getheader("ETag")
                strong_etag = etag if etag and not etag.startswith("W/") else None
                metadata = {"url": url, "strong_etag": strong_etag,
                            "last_modified": response.getheader("Last-Modified"),
                            "total_bytes": total_size}
                metadata_path.write_text(json.dumps(metadata, sort_keys=True))
                with partial.open("ab" if offset else "wb") as output:
                    total = offset
                    while True:
                        if cancel:cancel()
                        block = response.read(min(1024 * 1024, limit - total + 1))
                        if not block:
                            break
                        self.bytes_fetched += len(block)
                        total += len(block)
                        if total > limit:
                            raise ValueError("HTTPS response exceeds fetch budget")
                        output.write(block)
                        if progress:progress(total)
                if length is not None and total - offset != length:
                    raise ValueError("HTTPS response ended before Content-Length")
                if range_end is not None and total != total_size:
                    raise ValueError("HTTPS range ended before the complete resource")
                result = cache.commit(identity, partial,
                                      fingerprint_type="etag" if etag else "last_modified" if metadata["last_modified"] else "none",
                                      fingerprint=etag or metadata["last_modified"], expected_sha256=expected_sha256)
                metadata_path.unlink(missing_ok=True)
                return result
            finally:
                connection.close()
        raise ValueError("Too many HTTPS redirects")
