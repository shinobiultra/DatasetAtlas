"""Bounded, read-only reachability probe for candidate source URLs.

One HEAD per hop (a 1-byte ranged GET when the server refuses HEAD or answers it with an empty body), manual
redirects, credential-free, no payload ever downloaded. Bulk fetching stays on `storage/https.py`; this is a
research-time tool. Each hop's host is resolved and checked before the request, but httpx resolves it again to
connect, so a hostile DNS server could answer differently the second time (a rebinding window the project's pinned
fetcher closes and this probe does not).
"""
from __future__ import annotations

import http.cookiejar
import ipaddress
import re
import socket
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urljoin, urlsplit

import httpx

ProbeStatus = Literal["reachable", "empty_response", "gated_or_forbidden", "gone",
                      "unreachable", "redirect_refused", "server_error"]

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
RANGE_FALLBACK_STATUSES = frozenset({403, 405, 501})
HEADERS = {"User-Agent": "DatasetAtlas-source-probe/0.1", "Accept": "*/*", "Accept-Encoding": "identity"}


@dataclass(frozen=True)
class ProbeOutcome:
    url: str
    status: ProbeStatus
    http_status: int | None
    content_length: int | None
    content_type: str | None
    etag: str | None
    content_digest: str | None
    final_host: str | None
    error: str | None
    elapsed_s: float
    checked_at_utc: str


@dataclass(frozen=True)
class _Reply:
    status: int
    headers: httpx.Headers
    length: int | None
    host: str


class _Refused(Exception):
    """The probe declined to contact a host (policy), which says nothing about the source."""


def classify_probe(*, http_status: int | None, error: str | None, content_length: int | None,
                   content_type: str | None, redirect_refused: bool) -> ProbeStatus:
    """Only the refusal flag, the HTTP status and a zero length decide the class.

    A timeout or DNS failure is `unreachable` (transient), never a gate. 429/408 and 5xx are `server_error`. Any
    other unexpected status is not evidence of a gate or a removal, so it also reads `unreachable`.
    """
    if redirect_refused:
        return "redirect_refused"
    if http_status is None:
        return "unreachable"
    if 200 <= http_status < 300:
        return "empty_response" if content_length == 0 else "reachable"
    if http_status in (401, 402, 403, 451):
        return "gated_or_forbidden"
    if http_status in (404, 410):
        return "gone"
    if http_status >= 500 or http_status in (408, 429):
        return "server_error"
    return "unreachable"


def _new_client(timeout: float) -> httpx.Client:
    """No environment proxies or netrc, no redirects, and a cookie jar that accepts nothing."""
    jar = http.cookiejar.CookieJar(http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))
    return httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False, cookies=jar)


def _system_resolver(host: str) -> list[str]:
    return [str(entry[4][0]) for entry in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)]


def _check_destination(url: str, resolver: Callable[[str], Sequence[str]]) -> str:
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        _ = parts.port
    except ValueError as error:
        raise _Refused(f"malformed URL: {error}") from None
    if parts.scheme.lower() not in ("http", "https") or not host:
        raise _Refused(f"only http(s) URLs with a host are probed, not {parts.scheme or 'a bare string'}")
    if parts.username or parts.password:
        raise _Refused("URLs carrying credentials are not probed")
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        addresses = list(resolver(host))
    if not addresses:
        raise OSError(f"{host} did not resolve")
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        if not (getattr(parsed, "ipv4_mapped", None) or parsed).is_global:
            raise _Refused(f"{host} resolves to the non-global address {address}")
    return host


def _length(response: httpx.Response, *, sniff_body: bool) -> int | None:
    if response.status_code == 206:
        match = re.fullmatch(r"bytes [0-9]+-[0-9]+/([0-9]+|\*)", response.headers.get("content-range", "").strip())
        return int(match[1]) if match and match[1] != "*" else None
    declared = response.headers.get("content-length", "").strip()
    if re.fullmatch(r"[0-9]+", declared):
        return int(declared)
    if sniff_body and response.status_code == 200 and not next(response.iter_raw(1), b""):
        return 0
    return None


def _request(client: httpx.Client, url: str, host: str) -> _Reply:
    with client.stream("HEAD", url, headers=HEADERS) as response:
        reply = _Reply(response.status_code, response.headers, _length(response, sniff_body=False), host)
    # Some servers answer HEAD with content-length 0 for a page that GET serves (Google Drive folders), so an empty
    # HEAD is confirmed with the same 1-byte ranged GET before it is called empty.
    if reply.status in RANGE_FALLBACK_STATUSES or (200 <= reply.status < 300 and reply.length == 0):
        with client.stream("GET", url, headers={**HEADERS, "Range": "bytes=0-0"}) as response:
            reply = _Reply(response.status_code, response.headers, _length(response, sniff_body=True), host)
    return reply


def _unquote(value: str | None) -> str | None:
    value = (value or "").strip()
    return None if not value or value.startswith("W/") else value.strip('"') or None


def _digest(headers: httpx.Headers) -> str | None:
    return (_unquote(headers.get("digest")) or _unquote(headers.get("content-md5"))
            or _unquote(headers.get("x-linked-etag")))


def _probe_once(url: str, client: httpx.Client, resolver: Callable[[str], Sequence[str]], max_redirects: int) -> ProbeOutcome:
    reply: _Reply | None = None
    error: str | None = None
    refused = False
    current = url
    try:
        for _ in range(max_redirects + 1):
            host = _check_destination(current, resolver)
            reply = _request(client, current, host)
            location = reply.headers.get("location")
            if reply.status not in REDIRECT_STATUSES:
                break
            if not location:
                raise _Refused(f"HTTP {reply.status} redirect without a Location header")
            current = urljoin(current, location)
        else:
            raise _Refused(f"more than {max_redirects} redirects")
    except _Refused as refusal:
        error, refused = str(refusal), True
    except (httpx.HTTPError, httpx.InvalidURL, OSError) as failure:
        error = f"{type(failure).__name__}: {failure}"
        reply = None
    answered = reply if reply is not None and not refused else None
    status = classify_probe(http_status=reply.status if reply else None, error=error,
                            content_length=answered.length if answered else None,
                            content_type=answered.headers.get("content-type") if answered else None, redirect_refused=refused)
    if answered is not None and status == "unreachable":
        error = f"unexpected HTTP {answered.status}"
    return ProbeOutcome(
        url=url, status=status, http_status=reply.status if reply else None,
        content_length=answered.length if answered else None,
        content_type=answered.headers.get("content-type") if answered else None,
        etag=answered.headers.get("etag") if answered else None,
        content_digest=_digest(answered.headers) if answered else None,
        final_host=reply.host if reply else None, error=error, elapsed_s=0.0, checked_at_utc="")


def _transient(outcome: ProbeOutcome) -> bool:
    return outcome.status == "server_error" or (outcome.status == "unreachable" and outcome.http_status is None)


def probe_url(url: str, *, timeout: float = 15.0, attempts: int = 2, max_redirects: int = 4,
              client: httpx.Client | None = None,
              resolver: Callable[[str], Sequence[str]] | None = None) -> ProbeOutcome:
    """Classify one URL. Transport failures and 5xx are retried up to `attempts`; definite answers are not.

    A caller-supplied `client` is used as given (tests pass a MockTransport client) and must carry no credentials.
    """
    if attempts < 1 or max_redirects < 0 or timeout <= 0:
        raise ValueError("attempts and timeout must be positive and max_redirects non-negative")
    started = time.monotonic()
    owned = client is None
    session = client or _new_client(timeout)
    try:
        outcome = _probe_once(url, session, resolver or _system_resolver, max_redirects)
        for _ in range(attempts - 1):
            if not _transient(outcome):
                break
            outcome = _probe_once(url, session, resolver or _system_resolver, max_redirects)
    finally:
        if owned:
            session.close()
    return replace(outcome, elapsed_s=round(time.monotonic() - started, 3),
                   checked_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
