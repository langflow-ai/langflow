from __future__ import annotations

import gzip
import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import LargeBinary
from sqlalchemy.types import TypeDecorator

from langflow.services.database.models.flow_version.exceptions import FlowVersionSerializationError

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import Dialect

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


class GzippedJSON(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: dict[str, Any] | None, dialect: Dialect) -> bytes | None:  # noqa: ARG002
        return pack(value)

    def process_result_value(self, value: bytes | None, dialect: Dialect) -> dict[str, Any] | None:  # noqa: ARG002
        return unpack(value)
