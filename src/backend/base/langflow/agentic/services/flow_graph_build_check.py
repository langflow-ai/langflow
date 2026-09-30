"""Tier-2: build the graph to validate it WITHOUT running it.

`build_graph_from_data` constructs the Graph (`Graph.from_payload`),
instantiating every component and validating edges/handles at build
time. The LLM only executes later inside `vertex.build()`, which this
never triggers. So awaiting the build alone is a deterministic,
zero-LLM-token check for code/wiring/config defects. Any exception is
the deterministic build error — surfaced, never raised onward (a
validator must never break the build path).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lfx.log.logger import logger

from langflow.api.utils.flow_utils import build_graph_from_data


@dataclass(frozen=True)
class BuildCheckResult:
    """Outcome of the Tier-2 graph-construction check."""

    ok: bool
    error: str | None = None


async def build_check(*, flow: dict[str, Any], flow_id: str, user_id: str | None) -> BuildCheckResult:
    """Construct the flow's graph (no vertex run) to catch build errors.

    Args:
        flow: The working-flow dict.
        flow_id: The flow id (build_graph_from_data needs it).
        user_id: The owning user (for user-scoped component resolution).

    Returns:
        ``BuildCheckResult(ok=True)`` if the graph constructs, else
        ``ok=False`` with the deterministic build error message.
    """
    payload = (flow or {}).get("data") or {}
    flow_name = (flow or {}).get("name") or "Assistant Flow"
    try:
        await build_graph_from_data(flow_id, payload, flow_name=flow_name, user_id=user_id)
    except Exception as exc:  # noqa: BLE001 — the build error IS the result; never propagate
        logger.warning("assistant.flow_validation.tier2_build_failed flow_id=%s: %s", flow_id, exc)
        return BuildCheckResult(ok=False, error=str(exc))
    return BuildCheckResult(ok=True)
