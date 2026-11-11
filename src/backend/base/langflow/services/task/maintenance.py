"""Bind a worker's repair exception to a server-signed task identity."""

from __future__ import annotations

import hashlib
import hmac
import json
from uuid import UUID

from langflow.api.utils.migration_pause import admitted_maintenance_caller
from langflow.services.deps import get_settings_service

MAINTENANCE_HEADER = "langflow_maintenance_caller"


def _signature(caller: str, task_id: str, task_name: str) -> str:
    secret = get_settings_service().auth_settings.SECRET_KEY.get_secret_value()
    payload = json.dumps(["maintenance-v1", caller, task_id, task_name], separators=(",", ":"))
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def maintenance_task_headers(task_id: str, task_name: str) -> dict[str, dict[str, str]]:
    """Sign only the actual caller carried by an admitted server request."""
    caller = admitted_maintenance_caller()
    if caller is None:
        return {}
    value = str(caller)
    return {MAINTENANCE_HEADER: {"caller": value, "signature": _signature(value, task_id, task_name)}}


def verified_task_caller(headers: object, task_id: str, task_name: str) -> UUID | None:
    """Verify the envelope before rechecking current user privileges in the worker."""
    if not isinstance(headers, dict) or not isinstance(envelope := headers.get(MAINTENANCE_HEADER), dict):
        return None
    caller, signature = envelope.get("caller"), envelope.get("signature")
    if not isinstance(caller, str) or not isinstance(signature, str):
        return None
    if not hmac.compare_digest(signature, _signature(caller, task_id, task_name)):
        return None
    try:
        return UUID(caller)
    except ValueError:
        return None
