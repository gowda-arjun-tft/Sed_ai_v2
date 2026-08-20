from __future__ import annotations

import hashlib
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


def idna_host(host: str) -> str:
    """Punycode a host so non-ASCII domains resolve.

    Without this a .рф, .中国 or .السعودية address simply fails to resolve, which
    silently removes whole national registries from reach.
    """
    if not host or host.isascii():
        return host
    try:
        return host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return host


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.casefold()
    host = idna_host((parts.hostname or "").casefold())
    try:
        port = parts.port
    except ValueError:
        # A malformed port such as http://host:abc/ must not raise out of a
        # model-supplied URL.
        port = None
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = parts.path or "/"
    return urlunsplit((scheme, host, path, parts.query, ""))


def hit_id(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:16]


def validate_public_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme.casefold() not in {"http", "https"}:
        raise ValueError("only http and https sources are allowed")
    if parts.username or parts.password or not parts.hostname:
        raise ValueError("source URL credentials or missing hosts are not allowed")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(idna_host(parts.hostname), parts.port or 443)
        }
    except socket.gaierror as error:
        raise ValueError(f"source host could not be resolved: {parts.hostname}") from error
    if not addresses or any(not ipaddress.ip_address(value).is_global for value in addresses):
        raise ValueError("source host resolves to a non-public address")
    return normalize_url(url)
