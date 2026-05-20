"""Name validation, error helpers, and misc utilities for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, NoReturn, TypeVar
from uuid import uuid4

from fastapi import HTTPException
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.exceptions import (
    DeploymentError,
    DeploymentServiceError,
    InvalidContentError,
    OperationNotSupportedError,
)
from lfx.services.adapters.deployment.exceptions import (
    raise_as_deployment_error as raise_deployment_error_from_status,
)
from lfx.services.adapters.deployment.schema import _normalize_and_validate_id

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    WXO_SANITIZE_RE,
    WXO_TRANSLATE,
    ErrorPrefix,
)

if TYPE_CHECKING:
    from lfx.services.adapters.deployment.schema import (
        ConfigListParams,
        SnapshotListParams,
    )

logger = logging.getLogger(__name__)

LANGFLOW_WXO_RESOURCE_NAME_PREFIX = "langflow_"
T = TypeVar("T")


def normalize_wxo_name(s: str) -> str:
    return WXO_SANITIZE_RE.sub("", s.translate(WXO_TRANSLATE))


def normalize_wxo_display_name_segment(display_name: str, *, resource: str) -> str:
    """Normalize the display label segment used in Langflow-managed wxO names."""
    normalized_display_name = normalize_wxo_name(display_name).strip("_")
    if normalized_display_name:
        return normalized_display_name
    normalized_resource = normalize_wxo_name(resource).strip("_").lower()
    if not normalized_resource:
        msg = (
            "Display name did not include any alphanumeric characters, so fallback naming used the 'resource' "
            "argument. The 'resource' argument must include at least one alphanumeric character. "
            f"Received: '{resource}'"
        )
        raise InvalidContentError(message=msg)
    return normalized_resource


def build_langflow_wxo_resource_name(display_name: str, *, resource: str) -> str:
    """Build a Langflow-managed wxO technical name from a display label."""
    normalized_display_name = normalize_wxo_display_name_segment(display_name, resource=resource)
    return f"{LANGFLOW_WXO_RESOURCE_NAME_PREFIX}{normalized_display_name}_{uuid4().hex[:8]}"


def validate_wxo_name(name: str, *, field_label: str) -> str:
    """Normalize and validate a wxO resource name."""
    normalized_name = normalize_wxo_name(str(name))
    if not normalized_name:
        msg = f"{field_label} must include at least one alphanumeric character."
        raise InvalidContentError(message=msg)
    if not normalized_name[0].isalpha():
        msg = f"{field_label} must start with a letter."
        raise InvalidContentError(message=msg)
    return normalized_name


def ensure_field_not_none(value: T | None, *, field_label: str) -> T:
    """Validate that an explicitly provided field is not null."""
    if value is None:
        msg = f"{field_label} cannot be set to null."
        raise InvalidContentError(message=msg)
    return value


def ensure_field_not_empty(value: str | None, *, field_label: str) -> str:
    """Validate that an explicitly provided string field is neither null nor blank."""
    field_value = ensure_field_not_none(value, field_label=field_label)
    if not field_value.strip():
        msg = f"{field_label} cannot be empty."
        raise InvalidContentError(message=msg)
    return field_value


def validate_technical_name(name: str | None, *, field_label: str) -> str:
    """Validate a caller-provided wxO technical name without rewriting it."""
    technical_name = ensure_field_not_none(name, field_label=field_label)
    if not technical_name:
        msg = f"{field_label} must include at least one alphanumeric character."
        raise InvalidContentError(message=msg)
    if not technical_name[0].isalpha():
        msg = f"{field_label} must start with a letter."
        raise InvalidContentError(message=msg)
    if WXO_SANITIZE_RE.search(technical_name):
        msg = f"{field_label} must only contain letters, numbers, and underscores."
        raise InvalidContentError(message=msg)
    return technical_name


def validate_description(description: str | None, *, field_label: str) -> str | None:
    """Validate an explicit description update."""
    if description is not None and not description.strip():
        msg = f"{field_label} cannot be empty."
        raise InvalidContentError(message=msg)
    return description


def resolve_agent_description(description: str | None, *, agent_display_name: str) -> str:
    """Resolve the required description content used for agent create payloads.

    wxO does not allow null or empty descriptions.
    """
    if description and (desc := description.strip()):
        return desc
    return f"Langflow deployment {agent_display_name}"


def require_tool_id(tool_response: dict[str, Any]) -> str:
    tool_id = tool_response.get("id")
    if not tool_id:
        msg = "wxO did not return a tool id for snapshot creation."
        raise InvalidContentError(message=msg)
    return tool_id


def dedupe_list(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def normalize_and_dedupe_ids(values: list[Any] | None, *, field_name: str) -> list[str]:
    """Normalize id values to non-empty strings and dedupe while preserving order."""
    if not values:
        return []
    return dedupe_list([_normalize_and_validate_id(str(value), field_name=field_name) for value in values])


def require_single_deployment_id(
    params: ConfigListParams | SnapshotListParams | None,
    *,
    resource_label: str,
) -> str:
    deployment_ids = params.deployment_ids if params else None
    if not deployment_ids:
        msg = f"watsonx Orchestrate {resource_label} listing requires exactly one deployment_id."
        raise OperationNotSupportedError(message=msg)
    if len(deployment_ids) != 1:
        msg = (
            f"watsonx Orchestrate {resource_label} listing currently supports "
            "exactly one deployment_id and only deployment-scoped listing."
        )
        raise InvalidContentError(message=msg)
    return _normalize_and_validate_id(str(deployment_ids[0]), field_name="deployment_id")


def extract_error_detail(response_text: str) -> str:
    """Extract a human-readable error detail from a ClientAPIException response.

    The response body may contain a ``detail`` value that is a string, a dict
    with a ``msg`` key, or a list of such dicts.  This helper normalises all
    three shapes into a single value suitable for inclusion in an error message.
    """
    fallback = response_text or "<empty response body>"
    try:
        payload = json.loads(response_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    if not isinstance(payload, dict):
        return fallback

    detail = payload.get("detail")
    if detail in (None, "", [], {}):
        for field in ("message", "details", "error"):
            detail = payload.get(field)
            if detail not in (None, "", [], {}):
                break
        else:
            return fallback

    if isinstance(detail, list):
        detail = detail[0] if detail else None
    if isinstance(detail, dict):
        detail = detail.get("msg") or detail

    return str(detail) if detail not in (None, "", [], {}) else fallback


def _resolve_exc_detail(exc: ClientAPIException | HTTPException) -> str:
    if isinstance(exc, ClientAPIException):
        raw_text = getattr(exc.response, "text", "")
        return extract_error_detail(raw_text)
    return str(extract_error_detail(str(exc.detail)))


def _resolve_exc_status_code(exc: ClientAPIException | HTTPException) -> int:
    if isinstance(exc, ClientAPIException):
        return int(exc.response.status_code)
    return int(exc.status_code)


def raise_as_deployment_error(
    exc: Exception,
    *,
    error_prefix: ErrorPrefix,
    log_msg: str,
    resource: str | None = None,
    resource_name: str | None = None,
    pass_through: tuple[type[DeploymentServiceError], ...] = (),
) -> NoReturn:
    if isinstance(exc, pass_through):
        raise exc
    if isinstance(exc, DeploymentServiceError):
        logger.exception(log_msg)
        msg = f"{error_prefix.value} Please check server logs for details."
        raise DeploymentError(message=msg, error_code="deployment_error") from exc
    if isinstance(exc, (ClientAPIException, HTTPException)):
        status_code = _resolve_exc_status_code(exc)
        detail = _resolve_exc_detail(exc)
        raise_deployment_error_from_status(
            status_code=status_code,
            detail=detail,
            message_prefix=error_prefix.value,
            resource=resource,
            resource_name=resource_name,
            cause=exc,
        )
    logger.exception(log_msg)
    msg = f"{error_prefix.value} Please check server logs for details."
    raise DeploymentError(message=msg, error_code="deployment_error") from exc


def build_agent_payload_from_values(
    *,
    agent_name: str,
    agent_display_name: str,
    description: str | None,
    tool_ids: list[str],
    llm: str,
) -> dict[str, Any]:
    return {
        "name": agent_name,
        "display_name": agent_display_name,
        "description": resolve_agent_description(description, agent_display_name=agent_display_name),
        "tools": tool_ids,
        "style": "default",
        "llm": llm,
    }
