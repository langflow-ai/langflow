"""Name validation, error helpers, and misc utilities for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import json
import secrets
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lfx.services.adapters.deployment.exceptions import InvalidContentError

if TYPE_CHECKING:
    from lfx.services.adapters.deployment.schema import BaseDeploymentData

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    _WXO_SANITIZE_RE,
    _WXO_TRANSLATE,
    DEFAULT_WXO_AGENT_LLM,
    RANDOM_PREFIX_LENGTH_RANGE,
)


def normalize_wxo_name(s: str) -> str:
    return _WXO_SANITIZE_RE.sub("", s.translate(_WXO_TRANSLATE))


def validate_wxo_name(name: str) -> str:
    """Normalize and validate a WXO resource name."""
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
    caller_prefix: str | None = None,
) -> str:
    """Determine the resource name prefix for WxO resource creation.

    If *caller_prefix* is provided it is validated and used directly.
    Otherwise a random prefix of the form ``lf_{hex}_`` is generated
    as a fallback.
    """
    if caller_prefix is not None:
        if not isinstance(caller_prefix, str) or not caller_prefix.strip():
            msg = "global_resource_name_prefix must be a non-empty string."
            raise InvalidContentError(message=msg)
        validated = normalize_wxo_name(caller_prefix)
        if not validated:
            msg = "global_resource_name_prefix must contain at least one alphanumeric character."
            raise InvalidContentError(message=msg)
        if not validated[0].isalpha():
            msg = "global_resource_name_prefix must start with a letter."
            raise InvalidContentError(message=msg)
        return validated

    random_length = secrets.choice(RANDOM_PREFIX_LENGTH_RANGE)
    return f"lf_{uuid4().hex[:random_length]}_"


def require_tool_id(tool_response: dict[str, Any]) -> str:
    tool_id = tool_response.get("id")
    if not tool_id:
        msg = "WXO did not return a tool id for snapshot creation."
        raise ValueError(msg)
    return tool_id


def dedupe_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def extract_error_detail(response_text: str) -> str | dict:
    """Extract a human-readable error detail from a ClientAPIException response.

    The response body may contain a ``detail`` value that is a string, a dict
    with a ``msg`` key, or a list of such dicts.  This helper normalises all
    three shapes into a single value suitable for inclusion in an error message.
    """
    try:
        detail = json.loads(response_text).get("detail")
    except (TypeError, ValueError, json.JSONDecodeError):
        return response_text
    if detail and isinstance(detail, list):
        detail = detail[0]
    if isinstance(detail, dict):
        detail = detail.get("msg") or detail
    return detail


def build_agent_payload(
    *,
    data: BaseDeploymentData,
    tool_ids: list[str],
) -> dict[str, Any]:
    if data.provider_spec is None:
        msg = "Deployment data must include provider_spec with a non-empty name and display_name."
        raise InvalidContentError(message=msg)
    return {
        "name": data.provider_spec["name"],
        "display_name": data.provider_spec["display_name"],
        "description": str(data.description or "").strip() or f"Langflow deployment {data.name}",
        "tools": tool_ids,
        "style": "default",
        # TODO: make configurable; the llm field is required by the wxo api
        # but retrieving available llms requires an extra api request.
        "llm": DEFAULT_WXO_AGENT_LLM,
    }


def extract_agent_tool_ids(agent: dict[str, Any]) -> list[str]:
    # Shape source:
    # - SDK/API agent payload uses "tools" as list[str] in this adapter flow.
    return [str(tool_id) for tool_id in agent.get("tools", []) if tool_id]
