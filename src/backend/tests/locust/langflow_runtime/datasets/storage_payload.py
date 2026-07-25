"""Bounded storage payload for SaveToFile / payload-echo axes.

Not committed as a file — call ``bounded_payload_text()`` when a test or
Locust run needs the body. Used by ``perf_payload_echo`` coverage in
``test_subsystem_coverage`` and by fixture_index dataset selectors.
"""

from __future__ import annotations

from tests.locust.langflow_runtime.flows.defaults import DEFAULT_PAYLOAD_FILENAME

STORAGE_PAYLOAD_BYTES = 4_096
STORAGE_PAYLOAD_UNIT = "PERF_PAYLOAD_V1:"

__all__ = [
    "DEFAULT_PAYLOAD_FILENAME",
    "STORAGE_PAYLOAD_BYTES",
    "STORAGE_PAYLOAD_UNIT",
    "bounded_payload_text",
]


def bounded_payload_text(*, size_bytes: int = STORAGE_PAYLOAD_BYTES) -> str:
    """Return a deterministic ASCII payload of exactly ``size_bytes`` characters."""
    if size_bytes < len(STORAGE_PAYLOAD_UNIT):
        msg = f"size_bytes={size_bytes} too small for storage payload unit"
        raise ValueError(msg)
    body = (STORAGE_PAYLOAD_UNIT * ((size_bytes // len(STORAGE_PAYLOAD_UNIT)) + 1))[:size_bytes]
    if len(body) != size_bytes:
        msg = f"rendered storage payload length {len(body)} != {size_bytes}"
        raise RuntimeError(msg)
    return body
