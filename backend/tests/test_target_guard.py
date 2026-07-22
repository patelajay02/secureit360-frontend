# backend/tests/test_target_guard.py
# SSRF / target-validation tests. Cover every required case:
#   localhost, private IPv4, private IPv6, cloud metadata IP, public domain,
#   public IP, DNS resolving to private IP, redirect from public domain to a
#   private IP, IPv4-mapped IPv6 private address, malformed hostnames.

import socket
import pytest
import httpx

from services import target_guard
from services.target_guard import (
    TargetValidationError,
    validate_hostname_format,
    validate_public_hostname,
    resolve_and_validate,
    assert_scannable,
    classify_ip,
    safe_get,
)


def _resolver_for(mapping):
    """Return a fake socket.getaddrinfo that maps hostname -> list of IPs."""
    def _fake(host, port, *args, **kwargs):
        ips = mapping.get(host)
        if ips is None:
            raise socket.gaierror(f"no fake record for {host}")
        out = []
        for ip in ips:
            fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
            sockaddr = (ip, port or 0, 0, 0) if fam == socket.AF_INET6 else (ip, port or 0)
            out.append((fam, socket.SOCK_STREAM, 6, "", sockaddr))
        return out
    return _fake


# ── IP literal classification ────────────────────────────────────────────────
@pytest.mark.parametrize("ip", [
    "127.0.0.1",          # loopback
    "10.0.0.5",           # RFC1918
    "192.168.1.1",        # RFC1918
    "172.16.0.1",         # RFC1918
    "100.64.0.1",         # CGNAT
    "169.254.169.254",    # cloud metadata / link-local
    "169.254.170.2",      # AWS ECS metadata
    "0.0.0.0",            # unspecified
    "::1",                # IPv6 loopback
    "fd00::1",            # IPv6 unique-local
    "fe80::1",            # IPv6 link-local
    "::ffff:10.0.0.1",    # IPv4-mapped IPv6 private
    "::ffff:127.0.0.1",   # IPv4-mapped IPv6 loopback
    "224.0.0.1",          # multicast
    "198.51.100.5",       # TEST-NET-2 documentation
])
def test_private_and_reserved_ips_blocked(ip):
    ok, _reason = classify_ip(ip)
    assert ok is False, f"{ip} should be blocked"


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700:4700::1111"])
def test_public_ips_allowed(ip):
    ok, _reason = classify_ip(ip)
    assert ok is True, f"{ip} should be allowed"


# ── Hostname format validation ───────────────────────────────────────────────
@pytest.mark.parametrize("bad", [
    "localhost",
    "foo.localhost",
    "server.local",
    "db.internal",
    "host.lan",
    "",
    "   ",
    "exa mple.com",           # space
    "http://example.com",     # scheme
    "example.com/path",       # path
    "user@example.com",       # credentials
    "example.com:8080",       # port
    "-example.com",           # bad label
    "example",                # not fully-qualified
    "foo_bar.com",            # underscore
])
def test_malformed_or_internal_hostnames_rejected(bad):
    with pytest.raises(TargetValidationError):
        validate_hostname_format(bad)


def test_localhost_literal_blocked():
    with pytest.raises(TargetValidationError):
        validate_hostname_format("127.0.0.1")  # via classify path
    # And metadata literal:
    with pytest.raises(TargetValidationError):
        validate_hostname_format("169.254.169.254")


def test_valid_public_hostname_format():
    kind, value = validate_hostname_format("Example.COM")
    assert kind == "host"
    assert value == "example.com"


def test_public_ip_literal_accepted():
    kind, value = validate_hostname_format("8.8.8.8")
    assert kind == "ip"
    assert value == "8.8.8.8"


# ── DNS resolution + validation ──────────────────────────────────────────────
def test_public_domain_resolves_ok(monkeypatch):
    monkeypatch.setattr(target_guard.socket, "getaddrinfo",
                        _resolver_for({"good.example": ["93.184.216.34"]}))
    ips = resolve_and_validate("good.example")
    assert ips == ["93.184.216.34"]
    assert validate_public_hostname("good.example") == "good.example"


def test_domain_resolving_to_private_ip_rejected(monkeypatch):
    monkeypatch.setattr(target_guard.socket, "getaddrinfo",
                        _resolver_for({"evil.example": ["10.0.0.5"]}))
    with pytest.raises(TargetValidationError):
        resolve_and_validate("evil.example")


def test_domain_resolving_to_mixed_public_and_private_rejected(monkeypatch):
    # Fail closed: one public + one private record must be rejected entirely.
    monkeypatch.setattr(target_guard.socket, "getaddrinfo",
                        _resolver_for({"mixed.example": ["93.184.216.34", "10.0.0.5"]}))
    with pytest.raises(TargetValidationError):
        resolve_and_validate("mixed.example")


def test_domain_resolving_to_mapped_ipv6_private_rejected(monkeypatch):
    monkeypatch.setattr(target_guard.socket, "getaddrinfo",
                        _resolver_for({"mapped.example": ["::ffff:127.0.0.1"]}))
    with pytest.raises(TargetValidationError):
        resolve_and_validate("mapped.example")


def test_unresolvable_domain_fails_closed(monkeypatch):
    monkeypatch.setattr(target_guard.socket, "getaddrinfo", _resolver_for({}))
    with pytest.raises(TargetValidationError):
        resolve_and_validate("nope.example")


def test_assert_scannable_ip_literal():
    normalized, ips = assert_scannable("8.8.8.8")
    assert normalized == "8.8.8.8"
    assert ips == ["8.8.8.8"]


# ── safe_get: SSRF-safe HTTP with redirect re-validation ─────────────────────
@pytest.mark.asyncio
async def test_safe_get_rejects_direct_private_host():
    # IP literal host that is private → rejected before any connection.
    with pytest.raises(TargetValidationError):
        await safe_get("http://10.0.0.5/")


@pytest.mark.asyncio
async def test_safe_get_rejects_metadata_host():
    with pytest.raises(TargetValidationError):
        await safe_get("http://169.254.169.254/latest/meta-data/")


@pytest.mark.asyncio
async def test_safe_get_rejects_redirect_to_private(monkeypatch):
    respx = pytest.importorskip("respx")
    monkeypatch.setattr(target_guard.socket, "getaddrinfo",
                        _resolver_for({"public.example": ["93.184.216.34"]}))
    with respx.mock:
        respx.get("https://public.example").mock(
            return_value=httpx.Response(302, headers={"location": "http://10.0.0.5/"})
        )
        with pytest.raises(TargetValidationError):
            await safe_get("https://public.example")


@pytest.mark.asyncio
async def test_safe_get_returns_body_for_public(monkeypatch):
    respx = pytest.importorskip("respx")
    monkeypatch.setattr(target_guard.socket, "getaddrinfo",
                        _resolver_for({"public.example": ["93.184.216.34"]}))
    with respx.mock:
        respx.get("https://public.example").mock(
            return_value=httpx.Response(200, headers={"server": "nginx"}, content=b"hello")
        )
        resp = await safe_get("https://public.example")
        assert resp.status_code == 200
        assert resp.headers.get("server") == "nginx"
        assert resp.content == b"hello"


@pytest.mark.asyncio
async def test_safe_get_rejects_credentialed_url():
    with pytest.raises(TargetValidationError):
        await safe_get("http://user:pass@example.com/")
