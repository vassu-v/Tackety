"""
Webhook URL validation - blocks SSRF via webhook registration.

Without this, /setup/webhook accepts any URL and Webhooks.dispatch_event()
will happily make a server-side POST request to it on every ticket event.
Combined with no auth (fixed separately, see engine/auth.py) that was a
straightforward way to make the server request internal/cloud-metadata
endpoints on your behalf. This restricts registered webhook targets to
public, non-loopback, non-private http(s) hosts.

Known limitation: this resolves the hostname once, at registration time.
A DNS-rebinding attack (hostname resolves to a public IP at registration,
then to a private IP at dispatch time) is not defended against here. For
the threat model of a self-hosted, developer-registered webhook endpoint,
that's an acceptable gap for now - it would need to be re-validated at
dispatch time (with redirects disabled) to fully close.
"""
import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}


def _is_unsafe_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparsable - reject rather than guess
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def is_safe_webhook_url(url: str) -> tuple[bool, str]:
    """
    Returns (is_safe, reason). reason is empty when is_safe is True.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "URL could not be parsed"

    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"scheme must be one of {sorted(ALLOWED_SCHEMES)}"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL has no hostname"

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        return False, f"hostname could not be resolved: {e}"

    resolved_ips = {info[4][0] for info in addr_infos}
    if not resolved_ips:
        return False, "hostname resolved to no addresses"

    for ip_str in resolved_ips:
        if _is_unsafe_ip(ip_str):
            return False, f"resolves to a private/internal address ({ip_str})"

    return True, ""
