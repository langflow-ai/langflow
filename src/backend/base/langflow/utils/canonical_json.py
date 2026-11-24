"""Deterministic JSON bytes and digests shared by every caller that hashes a payload.

A canonical JSON encoding sorts object keys and freezes whitespace so the same
logical value always serializes to the same bytes regardless of dict insertion
order. That determinism is what makes the encoding useful as an input to a
content hash, such as a manifest checksum, a request-replay digest, or a
connector-ingest idempotency key.

The defaults (``sort_keys=True``, tight separators, ``ensure_ascii=False``)
match the tightest of the call sites this module consolidates. A caller whose
existing digest depends on a looser encoding (default-spaced separators,
escaped non-ASCII, or a ``default`` fallback for non-JSON-native types) passes
the matching keyword so its byte output is unchanged.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_COMPACT_SEPARATORS = (",", ":")


def canonical_json_bytes(
    value: object,
    *,
    ensure_ascii: bool = False,
    separators: tuple[str, str] | None = _COMPACT_SEPARATORS,
    default: Callable[[object], object] | None = None,
) -> bytes:
    """Serialize ``value`` to deterministic JSON bytes with sorted keys."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=ensure_ascii,
        separators=separators,
        default=default,
    ).encode()


def canonical_json_digest(
    value: object,
    *,
    ensure_ascii: bool = False,
    separators: tuple[str, str] | None = _COMPACT_SEPARATORS,
    default: Callable[[object], object] | None = None,
) -> str:
    """Return the hex SHA-256 digest of ``value``'s canonical JSON encoding."""
    return hashlib.sha256(
        canonical_json_bytes(value, ensure_ascii=ensure_ascii, separators=separators, default=default)
    ).hexdigest()


__all__ = ["canonical_json_bytes", "canonical_json_digest"]
