"""Static Locust metric names for the performance suite."""

from __future__ import annotations

import re

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_HIGH_CARDINALITY_RE = re.compile(
    r"(session[_-]?id|job[_-]?id|request[_-]?id|run[_-]?id|"
    r"kb[_-]?[a-z0-9_-]*\d{4,}|"
    r"perf_kb_[a-z0-9_-]+|"
    r"[0-9a-f]{32})",
    re.IGNORECASE,
)
_MAX_NAME_LEN = 80


def metric_name(protocol: str, operation: str, workload: str, flow_class: str) -> str:
    """Build a bounded static Locust name: ``protocol:operation:workload:flow_class``."""
    parts = [protocol, operation, workload, flow_class]
    for part in parts:
        if not part or not str(part).strip():
            msg = f"metric name segments must be non-empty; got {parts!r}"
            raise ValueError(msg)
        text = str(part)
        if _UUID_RE.search(text) or _HIGH_CARDINALITY_RE.search(text):
            msg = f"metric name segment rejects high-cardinality value: {text!r}"
            raise ValueError(msg)
    name = ":".join(str(part) for part in parts)
    if len(name) > _MAX_NAME_LEN:
        msg = f"metric name exceeds {_MAX_NAME_LEN} chars: {name!r}"
        raise ValueError(msg)
    return name
