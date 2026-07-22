# backend/services/target_guard.py
# SecureIT360 — Central SSRF / target-validation and safe-outbound-request layer.
#
# EVERY scanner that touches a user-controlled target (DNS resolution, socket
# connect, HTTP(S) request, TLS certificate inspection) MUST go through this
# module. It fails CLOSED: any uncertainty → the target is rejected.
#
# What it enforces:
#   * Only well-formed public domains / explicitly-public IPs are accepted.
#   * localhost, loopback, private (RFC1918), link-local, CGNAT, multicast,
#     reserved, documentation/test ranges, IPv6 ULA/loopback/link-local,
#     IPv4-mapped-IPv6 private addresses, and cloud metadata (169.254.169.254)
#     are rejected.
#   * DNS is resolved BEFORE connecting and every resolved IP is validated.
#   * Redirects are NOT auto-trusted: each hop is re-parsed, re-resolved and
#     re-validated, under a strict redirect cap.
#   * TLS verification is ON. `verify=False` is never used for ordinary requests.
#   * Connect/read/total timeouts and a response-size cap are always applied.
#   * URLs with credentials, schemes, paths, or ports where a bare hostname is
#     expected are rejected.
#
# NOTE ON DNS REBINDING: resolve-then-validate before every hop (including the
# raw-socket TLS path, which pins to a validated IP) closes the static and
# redirect-based rebinding vectors and the tests exercise them. Full
# connection-level IP pinning for pooled httpx HTTPS requests is a Phase-1
# hardening; documented here rather than silently omitted.

import ipaddress
import re
import socket
import ssl
from typing import List, Tuple

import httpx

# ── Configuration ────────────────────────────────────────────────────────────
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 15.0
TOTAL_TIMEOUT = 20.0
MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 2_000_000  # 2 MB cap to prevent memory exhaustion

# Hostname label rules (RFC 1123), ASCII/LDH after IDNA encoding.
_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)"
    r"(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$"
)

# Hostname suffixes that must never be treated as public, scannable targets.
_INTERNAL_SUFFIXES = (
    ".localhost", ".local", ".internal", ".intranet", ".lan",
    ".corp", ".home", ".localdomain",
)

# Explicit cloud metadata endpoints (defence in depth; most are already covered
# by link-local, but multiple clouds use distinct addresses).
_METADATA_IPS = {
    "169.254.169.254",   # AWS / Azure / GCP / OpenStack / DigitalOcean
    "169.254.170.2",     # AWS ECS task metadata
    "100.100.100.200",   # Alibaba Cloud
    "fd00:ec2::254",     # AWS IMDS over IPv6
}

# Blocked IPv4 CIDRs (superset of ipaddress' built-in flags, made explicit).
_BLOCKED_V4 = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8",         # "this" network / unspecified
    "10.0.0.0/8",        # RFC1918 private
    "100.64.0.0/10",     # CGNAT (RFC6598)
    "127.0.0.0/8",       # loopback
    "169.254.0.0/16",    # link-local (incl. metadata)
    "172.16.0.0/12",     # RFC1918 private
    "192.0.0.0/24",      # IETF protocol assignments
    "192.0.2.0/24",      # TEST-NET-1 (documentation)
    "192.88.99.0/24",    # 6to4 relay anycast
    "192.168.0.0/16",    # RFC1918 private
    "198.18.0.0/15",     # benchmarking
    "198.51.100.0/24",   # TEST-NET-2 (documentation)
    "203.0.113.0/24",    # TEST-NET-3 (documentation)
    "224.0.0.0/4",       # multicast
    "240.0.0.0/4",       # reserved (incl. 255.255.255.255)
)]

# Blocked IPv6 CIDRs.
_BLOCKED_V6 = [ipaddress.ip_network(n) for n in (
    "::/128",            # unspecified
    "::1/128",           # loopback
    "::ffff:0:0/96",     # IPv4-mapped (also unwrapped separately)
    "64:ff9b::/96",      # NAT64
    "100::/64",          # discard-only
    "2001:db8::/32",     # documentation
    "2001::/23",         # IETF protocol assignments (Teredo, etc.)
    "fc00::/7",          # unique-local (ULA)
    "fe80::/10",         # link-local
    "ff00::/8",          # multicast
)]


class TargetValidationError(Exception):
    """Raised when a target is not a permitted public host. Fail closed."""


class SafeResponse:
    """Minimal response wrapper returned by safe_get (httpx-compatible surface)."""

    def __init__(self, status_code: int, headers: httpx.Headers, content: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = content

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        import json
        return json.loads(self.content or b"null")


# ── IP classification ────────────────────────────────────────────────────────
def _unwrap(ip: ipaddress._BaseAddress):
    """Unwrap IPv4-mapped and 6to4-embedded IPv6 to the underlying IPv4."""
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return ip.ipv4_mapped
        if ip.sixtofour is not None:
            return ip.sixtofour
    return ip


def ip_is_public(ip_value) -> bool:
    """True only if the address is a routable public address."""
    ok, _ = classify_ip(ip_value)
    return ok


def classify_ip(ip_value) -> Tuple[bool, str]:
    """Return (is_public, reason). Never raises for a valid address string."""
    try:
        ip = ipaddress.ip_address(str(ip_value).split("%")[0])  # strip zone id
    except ValueError:
        return (False, "not-an-ip")

    if str(ip) in _METADATA_IPS:
        return (False, "cloud-metadata")

    ip = _unwrap(ip)

    if str(ip) in _METADATA_IPS:
        return (False, "cloud-metadata")

    nets = _BLOCKED_V4 if ip.version == 4 else _BLOCKED_V6
    for net in nets:
        if ip in net:
            return (False, f"blocked-range:{net}")

    # Final safety net via the stdlib flags.
    if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
            or ip.is_reserved or ip.is_unspecified):
        return (False, "non-public")

    return (True, "public")


# ── Hostname validation ──────────────────────────────────────────────────────
def validate_hostname_format(user_input: str) -> Tuple[str, str]:
    """Validate a bare target. Returns (kind, value) where kind is 'ip'|'host'.

    Rejects schemes, paths, query strings, credentials, ports, whitespace,
    localhost, internal-only suffixes, and malformed hostnames. Raises
    TargetValidationError on any problem.
    """
    if not user_input or not isinstance(user_input, str):
        raise TargetValidationError("empty target")

    value = user_input.strip()
    if not value:
        raise TargetValidationError("empty target")

    # No URL structure, credentials, paths, or whitespace allowed here.
    for bad in ("://", "@", "/", "\\", "?", "#", " ", "\t", "\r", "\n"):
        if bad in value:
            raise TargetValidationError(
                "target must be a bare hostname (no scheme, path, credentials, or port)"
            )

    # IP literal? (bracketed IPv6 or plain)
    literal = value
    if literal.startswith("[") and literal.endswith("]"):
        literal = literal[1:-1]
    try:
        ip = ipaddress.ip_address(literal)
        ok, reason = classify_ip(ip)
        if not ok:
            raise TargetValidationError(f"IP address not permitted ({reason})")
        return ("ip", str(ip))
    except ValueError:
        pass  # not an IP literal → treat as hostname

    # A colon on a non-IP means a port was supplied.
    if ":" in value:
        raise TargetValidationError("ports are not permitted")

    host = value.lower().rstrip(".")

    # IDNA / punycode encode unicode hostnames, then enforce LDH charset.
    try:
        host = host.encode("idna").decode("ascii")
    except Exception:
        raise TargetValidationError("malformed hostname")

    if not _HOSTNAME_RE.match(host):
        raise TargetValidationError("malformed hostname")

    if host == "localhost" or host.endswith(_INTERNAL_SUFFIXES):
        raise TargetValidationError("internal/localhost hostnames are not permitted")

    if "." not in host:
        raise TargetValidationError("hostname must be a fully-qualified public domain")

    return ("host", host)


def resolve_and_validate(host: str) -> List[str]:
    """Resolve a hostname to all A/AAAA records and validate EVERY one.

    Fails closed: raises if resolution fails or if ANY resolved address is not
    a permitted public address (an attacker cannot mix one public + one private
    record to slip through).
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise TargetValidationError(f"could not resolve host: {host}")

    ips = sorted({info[4][0] for info in infos})
    if not ips:
        raise TargetValidationError(f"no addresses for host: {host}")

    for ip in ips:
        ok, reason = classify_ip(ip)
        if not ok:
            raise TargetValidationError(
                f"host {host} resolves to a non-public address ({reason})"
            )
    return ips


def validate_public_hostname(user_input: str) -> str:
    """Format-validate a target and (for hostnames) confirm it resolves only to
    public IPs. Returns the normalized hostname/IP. Raises TargetValidationError.
    """
    kind, value = validate_hostname_format(user_input)
    if kind == "host":
        resolve_and_validate(value)
    return value


def assert_scannable(user_input: str) -> Tuple[str, List[str]]:
    """Full pre-connection check. Returns (normalized_target, validated_ips)."""
    kind, value = validate_hostname_format(user_input)
    if kind == "ip":
        return (value, [value])
    ips = resolve_and_validate(value)
    return (value, ips)


# ── Safe TLS socket (used for certificate inspection, with IP pinning) ───────
def get_peer_certificate(hostname: str, port: int = 443, timeout: float = 10.0) -> dict:
    """Open a validated, IP-pinned TLS connection and return the peer cert dict.

    The connection is made to a resolved+validated IP with SNI/cert checking
    against the original hostname — closing the DNS-rebinding window for this
    path. TLS verification is ON (default context).
    """
    normalized, ips = assert_scannable(hostname)
    context = ssl.create_default_context()
    last_err = None
    for ip in ips:
        try:
            with socket.create_connection((ip, port), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=normalized) as ssock:
                    return ssock.getpeercert()
        except Exception as e:  # try the next validated IP
            last_err = e
    raise last_err if last_err else TargetValidationError("no reachable validated IP")


# ── Safe HTTP GET (resolve-validate before each hop; manual redirect handling)
async def safe_get(url: str, *, headers: dict = None, timeout: float = READ_TIMEOUT) -> SafeResponse:
    """Perform an SSRF-safe HTTP(S) GET.

    Validates the host (and all resolved IPs) before connecting, follows
    redirects manually re-validating each hop, enforces TLS verification,
    strict timeouts, and a response-size cap.
    """
    current = url.strip()
    timeout_cfg = httpx.Timeout(TOTAL_TIMEOUT, connect=CONNECT_TIMEOUT, read=timeout)

    for _hop in range(MAX_REDIRECTS + 1):
        parsed = httpx.URL(current)
        if parsed.scheme not in ("http", "https"):
            raise TargetValidationError("only http and https are permitted")
        if parsed.userinfo:
            raise TargetValidationError("URLs containing credentials are not permitted")
        host = parsed.host
        if not host:
            raise TargetValidationError("missing host in URL")

        # Validate + resolve + validate all IPs (fail closed).
        assert_scannable(host)

        async with httpx.AsyncClient(
            verify=True,
            follow_redirects=False,
            timeout=timeout_cfg,
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=0),
        ) as client:
            async with client.stream("GET", current, headers=headers or {}) as resp:
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        return SafeResponse(resp.status_code, resp.headers, b"")
                    current = str(httpx.URL(current).join(location))
                    continue  # re-validate the new destination on the next loop

                body = bytearray()
                async for chunk in resp.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        body = body[:MAX_RESPONSE_BYTES]
                        break
                return SafeResponse(resp.status_code, resp.headers, bytes(body))

    raise TargetValidationError("too many redirects")
