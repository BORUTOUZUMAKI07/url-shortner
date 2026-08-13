"""Shared SSRF-safety helpers for outbound server-side HTTP fetches.

Both the metadata worker (user-supplied original_url) and webhook delivery
(user-supplied endpoint URLs) fetch URLs the user controls. The hostname is
resolved and every address must be public; private/loopback/link-local/
multicast/reserved/unspecified (and IPv4-mapped IPv6 wrappers) are rejected so
internal infrastructure can't be probed.
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


async def _resolve_public(hostname: str) -> bool:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


async def is_safe_url(url: str) -> bool:
    """True if the URL is http(s) and its hostname resolves only to public IPs."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    return await _resolve_public(hostname)
