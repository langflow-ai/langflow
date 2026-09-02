from __future__ import annotations

import gzip
import json
from typing import Any

from langflow.services.database.models.flow_version.exceptions import FlowVersionSerializationError

COMPRESS_LEVEL = 6


def pack(data: dict[str, Any] | None) -> bytes | None:
    if data is None:
        return None
    try:
        encoded = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        msg = "Flow version data could not be serialized."
        raise FlowVersionSerializationError(msg) from exc
    return gzip.compress(encoded, COMPRESS_LEVEL)


def unpack(blob: bytes | None) -> dict[str, Any] | None:
    if blob is None:
        return None
    try:
        return json.loads(gzip.decompress(blob))
    except (OSError, EOFError, ValueError, UnicodeDecodeError) as exc:
        msg = "Flow version data could not be read."
        raise FlowVersionSerializationError(msg) from exc
