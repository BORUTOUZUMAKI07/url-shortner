"""Shared SSRF-safety helpers for outbound server-side HTTP fetches.

Both the metadata worker (user-supplied original_url) and webhook delivery
(user-supplied endpoint URLs) fetch URLs the user controls. To prevent both
simple and DNS-rebinding SSRF, hostnames are resolved ONCE and the HTTP request
is **pinned** to a single resolved public address — the connection is made to
that exact IP, never re-resolved by the HTTP client. If the hostname later
re-resolves (rebinding attack), it has no effect because the socket is already
established against the validated address.
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

import httpx


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def _resolve_public(hostname: str) -> bool:
    """True if the hostname currently resolves ONLY to public IPs."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not _is_public_ip(ip):
            return False
    return True


async def is_safe_url(url: str) -> bool:
    """True if the URL is http(s) and its hostname resolves only to public IPs."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False
    # Block redirects/restart unless we resolve again inside safe_fetch/safe_post.
    return await _resolve_public(parsed.hostname)


async def _pick_public_address(hostname: str, port: int) -> str | None:
    """Resolve a hostname and return a single public (host, port) to pin to."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            hostname, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        return None
    for family, _stype, _proto, _canon, sockaddr in infos:
        ip = ipaddress.ip_address(str(sockaddr[0]))
        if _is_public_ip(ip):
            return f"[{sockaddr[0]}]" if ":" in str(sockaddr[0]) else str(sockaddr[0])
    return None


def _pin_url(url: str, ip: str) -> tuple[str, str]:
    """Rewrite url to connect to `ip` while preserving the original Host.

    Returns (rewritten_request_url, original_host). The original hostname is
    sent as the Host header and used as the TLS SNI name so virtual hosts and
    certificates still resolve — but the TCP/TLS connection targets `ip`, the
    already-validated public address, eliminating the DNS-rebinding window.
    """
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = parts.port
    netloc = ip
    if port is not None:
        netloc = f"{netloc}:{port}"
    rewritten = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return rewritten, host


async def safe_fetch(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
    follow_redirects: bool = False,
    max_redirects: int = 3,
) -> httpx.Response | None:
    """Fetch a URL pinning the connection to a validated public address.

    Returns the httpx.Response, or None if the URL is unsafe/unresolvable.
    Redirects are followed manually (up to ``max_redirects``), re-validating
    each hop. Use :func:`safe_post` for deliveries; this mirrors httpx.get.
    """
    current = url
    for _ in range(max_redirects + 1):
        parts = urlsplit(current)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return None
        ip = await _pick_public_address(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
        if ip is None:
            return None
        pinned_url, host = _pin_url(current, ip)
        req_headers = dict(headers or {})
        req_headers.setdefault("Host", host)
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                verify=True,
                http2=False,
            ) as client:
                # Pass the original hostname for SNI so TLS certificates validate.
                resp = await client.get(
                    pinned_url,
                    headers=req_headers,
                    extensions={"sni_hostname": host},
                )
        except Exception:
            return None
        if resp.is_redirect:
            location = resp.headers.get("location")
            if not location:
                return resp
            base = resp.url
            current = str(base.join(location))
            continue
        return resp
    return None


async def safe_post(
    url: str,
    *,
    content: bytes = b"",
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> httpx.Response | None:
    """POST a URL pinning the connection to a validated public address.

    Returns the httpx.Response, or None if the URL is unsafe/unresolvable or
    the connection fails. Used for webhook deliveries (never follows redirects —
    a webhook endpoint that redirects to an internal service is rejected).
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    ip = await _pick_public_address(
        parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)
    )
    if ip is None:
        return None
    pinned_url, host = _pin_url(url, ip)
    req_headers = dict(headers or {})
    req_headers.setdefault("Host", host)
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=True, http2=False) as client:
            return await client.post(
                pinned_url,
                content=content,
                headers=req_headers,
                extensions={"sni_hostname": host},
            )
    except Exception:
        return None
