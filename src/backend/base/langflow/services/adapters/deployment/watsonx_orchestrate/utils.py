"""Name validation, error helpers, and misc utilities for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, NoReturn

from fastapi import HTTPException
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.exceptions import (
    DeploymentError,
    DeploymentServiceError,
    InvalidContentError,
    OperationNotSupportedError,
    raise_for_status_and_detail,
)
from lfx.services.adapters.deployment.schema import _normalize_and_validate_id

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    DEFAULT_WXO_AGENT_LLM,
    WXO_SANITIZE_RE,
    WXO_TRANSLATE,
    ErrorPrefix,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lfx.services.adapters.deployment.schema import (
        BaseDeploymentData,
        ConfigListParams,
        SnapshotListParams,
    )

logger = logging.getLogger(__name__)


def normalize_wxo_name(s: str) -> str:
    return WXO_SANITIZE_RE.sub("", s.translate(WXO_TRANSLATE))


def validate_wxo_name(name: str) -> str:
    """Normalize and validate a wxO resource name."""
    normalized_name = normalize_wxo_name(str(name))
    if not normalized_name:
        msg = "Deployment name must include at least one alphanumeric character."
        raise InvalidContentError(message=msg)
    if not normalized_name[0].isalpha():
        msg = "Deployment name must start with a letter."
        raise InvalidContentError(message=msg)
    return normalized_name


def resolve_resource_name_prefix(
    *,
    caller_prefix: str,
) -> str:
    """Validate and return the caller-supplied resource name prefix for WxO resource creation."""
    if not isinstance(caller_prefix, str) or not caller_prefix.strip():
        msg = "resource_name_prefix must be a non-empty string."
        raise InvalidContentError(message=msg)
    validated = normalize_wxo_name(caller_prefix)
    if not validated:
        msg = "resource_name_prefix must contain at least one alphanumeric character."
        raise InvalidContentError(message=msg)
    if not validated[0].isalpha():
        msg = "resource_name_prefix must start with a letter."
        raise InvalidContentError(message=msg)
    return validated


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


def _require_single_deployment_id(
    params: ConfigListParams | SnapshotListParams | None,
    *,
    resource_label: str,
) -> str:
    deployment_ids = params.deployment_ids if params else None
    if not deployment_ids:
        msg = (
            f"watsonx Orchestrate {resource_label} listing requires exactly one "
            "deployment_id. Global listing is not supported by this adapter."
        )
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


def _resolve_exc_status_code(exc: ClientAPIException | HTTPException) -> int | None:
    if isinstance(exc, ClientAPIException):
        return int(getattr(exc.response, "status_code", 0) or 0) or None
    return int(exc.status_code)


def raise_as_deployment_error(
    exc: Exception,
    *,
    error_prefix: ErrorPrefix,
    log_msg: str,
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
        raise_for_status_and_detail(
            status_code=status_code,
            detail=detail,
            message_prefix=error_prefix.value,
        )
    logger.exception(log_msg)
    msg = f"{error_prefix.value} Please check server logs for details."
    raise DeploymentError(message=msg, error_code="deployment_error") from exc


def build_agent_payload(
    *,
    data: BaseDeploymentData,
    tool_ids: Sequence[str],
) -> dict[str, Any]:
    if data.provider_spec is None:
        msg = "Deployment data must include provider_spec with a non-empty name and display_name."
        raise InvalidContentError(message=msg)
    return {
        "name": data.provider_spec["name"],
        "display_name": data.provider_spec["display_name"],
        "description": str(data.description or "").strip() or f"Langflow deployment {data.name}",
        "tools": list(tool_ids),
        "style": "default",
        # TODO: make configurable; the llm field is required by the wxO api
        # but retrieving available llms requires an extra api request.
        "llm": DEFAULT_WXO_AGENT_LLM,
    }


def extract_agent_tool_ids(agent: dict[str, Any]) -> list[str]:
    # Shape source:
    # - SDK/API agent payload uses "tools" as list[str] in this adapter flow.
    return [str(tool_id) for tool_id in agent.get("tools", []) if tool_id]
