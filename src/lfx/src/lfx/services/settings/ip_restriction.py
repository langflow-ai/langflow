"""Utilities for parsing, validating and matching API-key IP allow-lists.

Supports three pattern forms, separated by semicolons:

- Literal IPv4 / IPv6 address (``203.0.113.5``, ``2001:db8::1``)
- CIDR network (``10.0.0.0/8``, ``2001:db8::/32``)
- IPv4 octet wildcard with ``%`` (``10.0.%.%`` → any 10.0.x.y)

Client addresses are normalized so that IPv4-mapped IPv6 ("::ffff:1.2.3.4")
matches IPv4 patterns transparently.
"""

from __future__ import annotations

import ipaddress

IPV4_DOT_SEPARATED_OCTET_COUNT = 4
IPV4_OCTET_MAX_VALUE = 255

_IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
_IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse_wildcard_ipv4(pattern: str) -> tuple[str, ...] | None:
    """Return the 4-tuple of octet patterns for a valid IPv4 wildcard, or None."""
    parts = pattern.split(".")
    if len(parts) != IPV4_DOT_SEPARATED_OCTET_COUNT:
        return None
    for p in parts:
        if p == "%":
            continue
        if not p.isdigit():
            return None
        if not (0 <= int(p) <= IPV4_OCTET_MAX_VALUE):
            return None
    return tuple(parts)


def _parse_pattern(raw: str) -> tuple[str, object]:
    """Parse a single allow-list pattern.

    Returns a ``(kind, value)`` tuple:

    - ``("exact", IPv4Address | IPv6Address)``
    - ``("cidr", IPv4Network | IPv6Network)``
    - ``("wildcard", tuple[str, str, str, str])``

    Raises:
        ValueError: if *raw* is not a valid pattern.
    """
    pattern = raw.strip()
    if not pattern:
        msg = "empty pattern"
        raise ValueError(msg)

    if "/" in pattern:
        try:
            return "cidr", ipaddress.ip_network(pattern, strict=False)
        except ValueError as e:
            msg = f"invalid CIDR {pattern!r}: {e}"
            raise ValueError(msg) from e

    if "%" in pattern:
        wildcard = _parse_wildcard_ipv4(pattern)
        if wildcard is None:
            msg = f"invalid IPv4 wildcard pattern {pattern!r} (expected 4 octets, digits 0-255 or '%')"
            raise ValueError(msg)
        return "wildcard", wildcard

    try:
        return "exact", ipaddress.ip_address(pattern)
    except ValueError as e:
        msg = f"invalid IP address {pattern!r}: {e}"
        raise ValueError(msg) from e


def validate_allowed_ips(value: str | None) -> str | None:
    """Validate and normalize a semicolon-separated allow-list string.

    Returns:
        ``None`` if *value* is falsy/empty; otherwise the normalized string
        (whitespace trimmed, entries rejoined with ``;``).

    Raises:
        ValueError: if any entry is not a valid IP, CIDR, or wildcard pattern.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None

    entries = [p.strip() for p in stripped.split(";") if p.strip()]
    if not entries:
        msg = "allow-list contains only separators"
        raise ValueError(msg)

    for entry in entries:
        _parse_pattern(entry)

    return ";".join(entries)


def normalize_client_ip(raw: str | None) -> str | None:
    """Return a canonical form of *raw*, unwrapping IPv4-mapped IPv6.

    Returns ``None`` for empty or invalid inputs.
    """
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    try:
        ip = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return str(ip.ipv4_mapped)
    return str(ip)


def _match_one(kind: str, parsed: object, ip: _IpAddress) -> bool:
    if kind == "exact":
        return ip == parsed
    if kind == "cidr":
        network = parsed  # type: ignore[assignment]
        # A v4 address cannot be in a v6 network, and vice versa.
        if isinstance(ip, ipaddress.IPv4Address) and isinstance(network, ipaddress.IPv4Network):
            return ip in network
        if isinstance(ip, ipaddress.IPv6Address) and isinstance(network, ipaddress.IPv6Network):
            return ip in network
        return False
    if kind == "wildcard":
        if not isinstance(ip, ipaddress.IPv4Address):
            return False
        octets = str(ip).split(".")
        return all(
            p in ("%", o)
            for p, o in zip(parsed, octets, strict=False)  # type: ignore[arg-type]
        )
    return False


def check_ip_restriction(allowed_ips: str | None, client_ip: str | None) -> bool:
    """Return ``True`` when *client_ip* is permitted by *allowed_ips*.

    - Empty/None allow-list → no restriction (``True``).
    - Non-empty allow-list with unknown/invalid *client_ip* → fail closed (``False``).
    - Invalid pattern entries → that single entry is ignored; a warning should
      be emitted by the caller at write/load time via :func:`validate_allowed_ips`.
    """
    if not allowed_ips:
        return True
    normalized = normalize_client_ip(client_ip)
    if normalized is None:
        return False

    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False

    entries = [p.strip() for p in allowed_ips.split(";") if p.strip()]
    if not entries:
        # Defensive: persisted values go through validate_allowed_ips, but be
        # explicit that "only-separators" is NOT allow-all.
        return False

    for entry in entries:
        try:
            kind, parsed = _parse_pattern(entry)
        except ValueError:
            continue
        if _match_one(kind, parsed, ip):
            return True
    return False
