"""User-supplied metadata helpers for Knowledge Base ingestion.

Two helpers:

* :func:`parse_user_metadata` decodes a JSON string from a multipart Form
  field, runs the rule set in :func:`validate_user_metadata`, and returns a
  dict — or raises :class:`fastapi.HTTPException` with a 422 status so the
  rejection surfaces as an inline form-validation error in the UI.
* :func:`parse_per_file_metadata` does the same for the
  ``per_file_metadata`` field, which carries a ``{filename: {...}}`` map of
  per-file overrides. Each inner dict goes through the same validator.

Mirrors the bounds in :mod:`langflow.utils.kb_constants` and is the only
metadata gate at the API boundary — :class:`KBIngestionHelper.perform_ingestion`
trusts that whatever it receives has already been validated.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

from langflow.utils.kb_constants import (
    KB_METADATA_MAX_ARRAY_LENGTH,
    KB_METADATA_MAX_KEY_LENGTH,
    KB_METADATA_MAX_KEYS,
    KB_METADATA_MAX_VALUE_LENGTH,
    KB_METADATA_RESERVED_KEYS,
)

_KEY_ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_")


def _is_valid_key(key: str) -> bool:
    if not key or len(key) > KB_METADATA_MAX_KEY_LENGTH:
        return False
    return all(c in _KEY_ALLOWED_CHARS for c in key)


def _validate_value(key: str, value: Any) -> None:
    if isinstance(value, (bool, int, float)):
        return
    if isinstance(value, str):
        if len(value) > KB_METADATA_MAX_VALUE_LENGTH:
            msg = f"Metadata value for '{key}' exceeds {KB_METADATA_MAX_VALUE_LENGTH} characters."
            raise HTTPException(status_code=422, detail=msg)
        return
    if isinstance(value, list):
        if len(value) > KB_METADATA_MAX_ARRAY_LENGTH:
            msg = f"Metadata array '{key}' exceeds {KB_METADATA_MAX_ARRAY_LENGTH} items."
            raise HTTPException(status_code=422, detail=msg)
        for entry in value:
            if not isinstance(entry, str):
                msg = f"Metadata array '{key}' must contain only strings."
                raise HTTPException(status_code=422, detail=msg)
            if len(entry) > KB_METADATA_MAX_VALUE_LENGTH:
                msg = f"Metadata array entry under '{key}' exceeds {KB_METADATA_MAX_VALUE_LENGTH} characters."
                raise HTTPException(status_code=422, detail=msg)
        return
    msg = f"Metadata value for '{key}' must be a string, number, bool, or string array; got {type(value).__name__}."
    raise HTTPException(status_code=422, detail=msg)


def validate_user_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Enforce the user-metadata contract on a decoded dict.

    Returns the same dict (a shallow copy is *not* made — callers may mutate
    safely once validation passes). Raises :class:`HTTPException` with a 422
    status on any violation so FastAPI surfaces an inline error.
    """
    if not isinstance(metadata, dict):
        msg = "Metadata must be a JSON object."
        raise HTTPException(status_code=422, detail=msg)
    if len(metadata) > KB_METADATA_MAX_KEYS:
        msg = f"Metadata exceeds the {KB_METADATA_MAX_KEYS} key limit."
        raise HTTPException(status_code=422, detail=msg)
    for key, value in metadata.items():
        if not isinstance(key, str) or not _is_valid_key(key):
            msg = (
                f"Metadata key {key!r} is invalid: must be 1-{KB_METADATA_MAX_KEY_LENGTH} "
                "lowercase alphanumeric or underscore characters."
            )
            raise HTTPException(status_code=422, detail=msg)
        if key in KB_METADATA_RESERVED_KEYS:
            msg = f"Metadata key '{key}' is reserved for ingestion-internal use."
            raise HTTPException(status_code=422, detail=msg)
        _validate_value(key, value)
    return metadata


def parse_user_metadata(raw: str | None) -> dict[str, Any]:
    """Decode + validate the ``metadata`` form field. Empty/None → ``{}``."""
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"Metadata is not valid JSON: {exc.msg}"
        raise HTTPException(status_code=422, detail=msg) from exc
    return validate_user_metadata(decoded)


def parse_per_file_metadata(raw: str | None) -> dict[str, dict[str, Any]]:
    """Decode + validate the ``per_file_metadata`` form field.

    Shape: ``{filename: {metadata_dict}, ...}``. Each inner dict goes through
    the same validator as run-level metadata, so per-file overrides obey the
    same key/value rules. Empty/None → ``{}``.
    """
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"Per-file metadata is not valid JSON: {exc.msg}"
        raise HTTPException(status_code=422, detail=msg) from exc
    if not isinstance(decoded, dict):
        msg = "Per-file metadata must be a JSON object keyed by filename."
        raise HTTPException(status_code=422, detail=msg)
    if len(decoded) > KB_METADATA_MAX_KEYS:
        msg = f"Per-file metadata exceeds the {KB_METADATA_MAX_KEYS} file limit."
        raise HTTPException(status_code=422, detail=msg)
    out: dict[str, dict[str, Any]] = {}
    for filename, file_metadata in decoded.items():
        if not isinstance(filename, str) or not filename:
            msg = "Per-file metadata keys must be non-empty filename strings."
            raise HTTPException(status_code=422, detail=msg)
        if not isinstance(file_metadata, dict):
            msg = f"Per-file metadata for {filename!r} must be a JSON object."
            raise HTTPException(status_code=422, detail=msg)
        out[filename] = validate_user_metadata(file_metadata)
    return out
