"""The source probe classifies what a bounded HEAD says and never downloads a payload; no network or DNS here."""
import socket

import httpx
import pytest

from dataset_atlas.registry.source_probe import ProbeOutcome, _new_client, classify_probe, probe_url

PUBLIC = "93.184.216.34"


def _resolver(mapping=None):
    mapping = mapping or {}
    return lambda host: mapping.get(host, [PUBLIC])


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _raising(error):
    def handler(request):
        raise error
    return _client(handler)


def _probe(status, *, headers=None, attempts=1, url="https://example.org/a.zip"):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(status, headers=headers or {})
    outcome = probe_url(url, client=_client(handler), resolver=_resolver(), attempts=attempts)
    return outcome, seen


def _probe_redirect(location, status=302, resolver=None):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.host == "example.org":
            return httpx.Response(status, headers={"location": location})
        return httpx.Response(200, headers={"content-length": "10"})
    outcome = probe_url("https://example.org/a.zip", client=_client(handler), resolver=resolver or _resolver(), attempts=1)
    return outcome, seen


@pytest.mark.parametrize("error", [httpx.ConnectTimeout("t"), httpx.ReadTimeout("t"), httpx.ConnectError("refused")])
def test_timeout_is_unreachable_not_gated(error):
    out = probe_url("https://example.org/a.zip", client=_raising(error), resolver=_resolver(), attempts=1)
    assert out.status == "unreachable" and out.http_status is None
    assert out.error.startswith(type(error).__name__) and out.final_host is None


@pytest.mark.parametrize("status,expected", [(401, "gated_or_forbidden"), (403, "gated_or_forbidden"), (404, "gone"), (410, "gone")])
def test_403_is_gated_or_forbidden_and_404_is_gone(status, expected):
    out, _ = _probe(status)
    assert out.status == expected and out.http_status == status and out.error is None


def test_200_empty_html_is_empty_response():
    out, _ = _probe(200, headers={"content-length": "0", "content-type": "text/html"})
    assert out.status == "empty_response" and out.content_length == 0 and out.content_type == "text/html"


def test_200_with_body_is_reachable_and_reports_length_and_type():
    out, seen = _probe(200, headers={"content-length": "123456", "content-type": "application/zip"})
    assert (out.status, out.http_status, out.content_length, out.content_type) == ("reachable", 200, 123456, "application/zip")
    assert out.final_host == "example.org" and out.error is None
    assert [request.method for request in seen] == ["HEAD"]


def test_empty_head_is_confirmed_by_a_one_byte_range_get_before_it_is_called_empty():
    out, seen = _probe(200, headers={"content-length": "0", "content-type": "text/html"})
    assert out.status == "empty_response" and [request.method for request in seen] == ["HEAD", "GET"]
    assert seen[1].headers["range"] == "bytes=0-0"


def test_head_that_claims_zero_length_but_get_serves_a_page_is_reachable():
    consumed = []

    def body():
        for chunk in (b"<", b"html>"):
            consumed.append(chunk)
            yield chunk

    def handler(request):
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-length": "0", "content-type": "text/html"})
        return httpx.Response(200, content=body(), headers={"content-type": "text/html"})
    out = probe_url("https://example.org/folder", client=_client(handler), resolver=_resolver(), attempts=1)
    assert out.status == "reachable" and out.content_length is None and consumed == [b"<"]


def test_200_without_length_is_reachable_with_unknown_length():
    out, _ = _probe(200, headers={"content-type": "application/zip"})
    assert out.status == "reachable" and out.content_length is None


def test_etag_and_digest_headers_are_reported():
    out, _ = _probe(200, headers={"content-length": "5", "etag": 'W/"abc"', "content-md5": "Q2hlY2sgSW50ZWdyaXR5IQ=="})
    assert out.etag == 'W/"abc"' and out.content_digest == "Q2hlY2sgSW50ZWdyaXR5IQ=="
    out, _ = _probe(200, headers={"content-length": "5", "digest": "sha-256=47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU="})
    assert out.content_digest == "sha-256=47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU="
    out, _ = _probe(200, headers={"content-length": "5", "etag": '"abc"', "x-linked-etag": '"' + "a" * 64 + '"'})
    assert out.etag == '"abc"' and out.content_digest == "a" * 64
    out, _ = _probe(200, headers={"content-length": "5", "etag": '"abc"'})
    assert out.content_digest is None


def test_missing_etag_and_digest_are_none():
    out, _ = _probe(200, headers={"content-length": "5"})
    assert out.etag is None and out.content_digest is None


def test_redirect_to_private_address_is_refused():
    out, seen = _probe_redirect("http://127.0.0.1/x")
    assert out.status == "redirect_refused" and "127.0.0.1" in out.error
    assert [request.url.host for request in seen] == ["example.org"]
    assert out.final_host == "example.org"


def test_redirect_to_hostname_resolving_to_private_or_mixed_address_is_refused():
    for addresses in (["10.0.0.5"], [PUBLIC, "169.254.169.254"], ["::1"], ["::ffff:127.0.0.1"]):
        out, seen = _probe_redirect("https://internal.example.net/x", resolver=_resolver({"internal.example.net": addresses}))
        assert out.status == "redirect_refused", addresses
        assert [request.url.host for request in seen] == ["example.org"]


def test_first_hop_to_a_non_global_address_is_refused_without_a_request():
    seen = []
    out = probe_url("http://localhost:8000/a", client=_client(lambda request: seen.append(request)),
                    resolver=_resolver({"localhost": ["127.0.0.1"]}), attempts=2)
    assert out.status == "redirect_refused" and seen == [] and out.http_status is None and out.final_host is None


@pytest.mark.parametrize("url", ["ftp://example.org/a", "file:///etc/passwd", "https://user:secret@example.org/a", "https:///a", "not a url"])
def test_unsupported_or_credentialed_urls_are_refused(url):
    seen = []
    out = probe_url(url, client=_client(lambda request: seen.append(request)), resolver=_resolver(), attempts=1)
    assert out.status == "redirect_refused" and seen == []


def test_redirect_to_public_host_is_followed_and_reports_the_final_host():
    out, seen = _probe_redirect("https://cdn.example.net/files/a.zip")
    assert out.status == "reachable" and out.final_host == "cdn.example.net" and out.content_length == 10
    assert [request.url.host for request in seen] == ["example.org", "cdn.example.net"]


def test_relative_redirect_stays_on_the_same_host_and_http_is_allowed():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.path == "/a":
            return httpx.Response(301, headers={"location": "/b?x=1"})
        return httpx.Response(200, headers={"content-length": "3"})
    out = probe_url("http://example.org/a", client=_client(handler), resolver=_resolver(), attempts=1)
    assert out.status == "reachable" and seen == ["http://example.org/a", "http://example.org/b?x=1"]


def test_redirect_loop_stops_at_max_redirects():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "/again"})
    out = probe_url("https://example.org/a", client=_client(handler), resolver=_resolver(), attempts=1, max_redirects=3)
    assert out.status == "redirect_refused" and "redirect" in out.error and len(seen) == 4


def test_redirect_without_location_is_refused():
    out, _ = _probe(302)
    assert out.status == "redirect_refused" and out.http_status == 302


def test_head_405_falls_back_to_one_byte_range_get_and_never_reads_more():
    seen, consumed = [], []

    def body():
        for chunk in (b"a", b"b", b"c"):
            consumed.append(chunk)
            yield chunk

    def handler(request):
        seen.append(request)
        if request.method == "HEAD":
            return httpx.Response(405)
        return httpx.Response(200, content=body(), headers={"content-type": "application/zip"})
    out = probe_url("https://example.org/a.zip", client=_client(handler), resolver=_resolver(), attempts=1)
    assert [request.method for request in seen] == ["HEAD", "GET"]
    assert seen[1].headers["range"] == "bytes=0-0"
    assert consumed == [b"a"]
    assert out.status == "reachable" and out.http_status == 200 and out.content_length is None


def test_range_get_reports_the_total_length_from_content_range():
    def handler(request):
        if request.method == "HEAD":
            return httpx.Response(501)
        return httpx.Response(206, content=b"x", headers={"content-range": "bytes 0-0/987654", "content-type": "application/zip"})
    out = probe_url("https://example.org/a.zip", client=_client(handler), resolver=_resolver(), attempts=1)
    assert (out.status, out.http_status, out.content_length) == ("reachable", 206, 987654)


def test_range_get_returning_an_empty_chunked_body_is_an_empty_response():
    def handler(request):
        return httpx.Response(405) if request.method == "HEAD" else httpx.Response(200, content=iter(()))
    out = probe_url("https://example.org/a.zip", client=_client(handler), resolver=_resolver(), attempts=1)
    assert out.status == "empty_response" and out.content_length == 0


def test_head_403_is_retried_once_as_a_ranged_get_and_still_forbidden_when_get_agrees():
    out, seen = _probe(403)
    assert out.status == "gated_or_forbidden"
    assert [request.method for request in seen] == ["HEAD", "GET"] and seen[1].headers["range"] == "bytes=0-0"


def test_head_403_but_get_works_is_reachable():
    def handler(request):
        return httpx.Response(403) if request.method == "HEAD" else httpx.Response(206, content=b"x", headers={"content-range": "bytes 0-0/50"})
    out = probe_url("https://example.org/a", client=_client(handler), resolver=_resolver(), attempts=1)
    assert out.status == "reachable" and out.content_length == 50


def test_5xx_is_server_error_and_retried_up_to_attempts():
    out, seen = _probe(503, attempts=3)
    assert out.status == "server_error" and out.http_status == 503 and len(seen) == 3
    out, seen = _probe(503, attempts=1)
    assert out.status == "server_error" and len(seen) == 1


def test_transient_failure_then_success_is_reachable():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("t")
        return httpx.Response(200, headers={"content-length": "9"})
    out = probe_url("https://example.org/a", client=_client(handler), resolver=_resolver(), attempts=2)
    assert out.status == "reachable" and len(calls) == 2


def test_definite_answers_are_not_retried():
    for status in (200, 404, 410, 401):
        out, seen = _probe(status, attempts=3)
        assert len(seen) == 1, status
    out, seen = _probe(403, attempts=3)
    assert len(seen) == 2
    out, seen = _probe_redirect("http://127.0.0.1/x")
    assert out.status == "redirect_refused" and len(seen) == 1


def test_resolver_failure_is_unreachable_and_never_contacts_the_host():
    def broken(host):
        raise socket.gaierror(-2, "Name or service not known")
    seen = []
    out = probe_url("https://example.org/a", client=_client(lambda request: seen.append(request)), resolver=broken, attempts=1)
    assert out.status == "unreachable" and "gaierror" in out.error and seen == []
    out = probe_url("https://example.org/a", client=_client(lambda request: seen.append(request)), resolver=lambda host: [], attempts=1)
    assert out.status == "unreachable" and seen == []


def test_requests_carry_no_credentials_and_ask_for_the_identity_encoding():
    out, seen = _probe(200, headers={"content-length": "1"})
    headers = seen[0].headers
    assert "authorization" not in headers and "cookie" not in headers and headers["accept-encoding"] == "identity"
    assert headers["user-agent"].startswith("DatasetAtlas")


def test_default_client_ignores_environment_credentials_and_refuses_cookies():
    client = _new_client(5.0)
    try:
        assert client.trust_env is False and client.follow_redirects is False
        client.cookies.extract_cookies(httpx.Response(200, headers={"set-cookie": "a=b; Domain=example.org"}, request=httpx.Request("GET", "https://example.org/")))
        assert len(client.cookies.jar) == 0
    finally:
        client.close()


def test_outcome_records_timing_and_a_utc_timestamp():
    out, _ = _probe(200, headers={"content-length": "1"})
    assert isinstance(out, ProbeOutcome) and out.url == "https://example.org/a.zip"
    assert out.elapsed_s >= 0 and out.checked_at_utc.endswith("Z") and len(out.checked_at_utc) == 20


def test_invalid_limits_are_rejected():
    for kwargs in ({"attempts": 0}, {"max_redirects": -1}, {"timeout": 0}):
        with pytest.raises(ValueError):
            probe_url("https://example.org/a", resolver=_resolver(), **kwargs)


@pytest.mark.parametrize("arguments,expected", [
    (dict(http_status=None, error="ConnectTimeout: t", content_length=None, content_type=None, redirect_refused=False), "unreachable"),
    (dict(http_status=200, error=None, content_length=0, content_type="text/html", redirect_refused=False), "empty_response"),
    (dict(http_status=200, error=None, content_length=0, content_type=None, redirect_refused=False), "empty_response"),
    (dict(http_status=200, error=None, content_length=10, content_type="text/html", redirect_refused=False), "reachable"),
    (dict(http_status=206, error=None, content_length=10, content_type=None, redirect_refused=False), "reachable"),
    (dict(http_status=401, error=None, content_length=None, content_type=None, redirect_refused=False), "gated_or_forbidden"),
    (dict(http_status=403, error=None, content_length=None, content_type=None, redirect_refused=False), "gated_or_forbidden"),
    (dict(http_status=451, error=None, content_length=None, content_type=None, redirect_refused=False), "gated_or_forbidden"),
    (dict(http_status=404, error=None, content_length=None, content_type=None, redirect_refused=False), "gone"),
    (dict(http_status=410, error=None, content_length=None, content_type=None, redirect_refused=False), "gone"),
    (dict(http_status=500, error=None, content_length=None, content_type=None, redirect_refused=False), "server_error"),
    (dict(http_status=503, error=None, content_length=None, content_type=None, redirect_refused=False), "server_error"),
    (dict(http_status=429, error=None, content_length=None, content_type=None, redirect_refused=False), "server_error"),
    (dict(http_status=400, error=None, content_length=None, content_type=None, redirect_refused=False), "unreachable"),
    (dict(http_status=304, error=None, content_length=None, content_type=None, redirect_refused=False), "unreachable"),
    (dict(http_status=302, error="refused", content_length=None, content_type=None, redirect_refused=True), "redirect_refused"),
    (dict(http_status=None, error="refused", content_length=None, content_type=None, redirect_refused=True), "redirect_refused"),
])
def test_classify_probe_table(arguments, expected):
    assert classify_probe(**arguments) == expected
