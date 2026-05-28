"""Normalize runtime ``global_vars`` payloads (WXO ADK / TRM contract)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.variable.request_scope import normalize_parsed_variables

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph

_LANGFLOW_REQUEST_VARIABLES_KEY = "LANGFLOW_REQUEST_VARIABLES"


def build_request_variables_from_global_vars(global_vars: dict[str, str] | None) -> dict[str, str]:
    """Flatten TRM-style ``global_vars`` into a single lookup map.

    TRM sends:
    - ``LANGFLOW_REQUEST_VARIABLES``: JSON blob of merged context + connection_details
    - raw credential keys (e.g. ``access_token``, ``wxo_github_access_token``)
    - ``x-langflow-global-var-*`` aliases

    Parsed JSON is applied first; explicit keys in *global_vars* (except the JSON
    blob key itself) override on collision. Under the TRM contract connection_details
    is sent as raw keys and context inside the JSON blob, so connection_details wins.
    """
    if not global_vars:
        return {}

    merged: dict[str, str] = {}
    raw_json = global_vars.get(_LANGFLOW_REQUEST_VARIABLES_KEY)
    if raw_json:
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.warning(
                f"Failed to parse {_LANGFLOW_REQUEST_VARIABLES_KEY} JSON ({exc}); "
                "credentials carried only in this blob will be unavailable."
            )
            parsed = None
        if isinstance(parsed, dict):
            merged.update(normalize_parsed_variables(parsed))
        elif parsed is not None:
            logger.warning(
                f"{_LANGFLOW_REQUEST_VARIABLES_KEY} must be a JSON object, got {type(parsed).__name__}; ignoring blob."
            )

    for key, value in global_vars.items():
        if key == _LANGFLOW_REQUEST_VARIABLES_KEY:
            continue
        normalized = key.strip() if isinstance(key, str) else ""
        if normalized:
            merged[normalized] = str(value)

    return merged


def apply_global_vars_to_graph(graph: Graph, global_vars: dict[str, str] | None) -> None:
    """Inject *global_vars* into ``graph.context['request_variables']``."""
    if not global_vars:
        return
    if "request_variables" not in graph.context:
        graph.context["request_variables"] = {}
    # TODO: stored verbatim, so blob-form vars (LANGFLOW_REQUEST_VARIABLES) are NOT flattened
    # here. The no-DB load_from_db path (load_from_env_vars reads graph.context) only resolves
    # direct keys, while the VariableService/ContextVar path (common.py) sees the flattened blob.
    # For parity, consider flattening via build_request_variables_from_global_vars. No current
    # impact: TRM also sends raw direct keys; defer unless a caller sends blob-only vars.
    graph.context["request_variables"].update(global_vars)
