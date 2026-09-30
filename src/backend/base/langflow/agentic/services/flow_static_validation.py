"""Tier-1 static validation of a built flow (zero LLM tokens).

Reuses Langflow's existing CLI validator
(``lfx.cli.validation.core.validate_flow_file`` →
STRUCTURAL → COMPONENTS → EDGE_TYPES → REQUIRED_INPUTS) instead of
reinventing it. The validator is file-based, so this serializes the
in-memory flow to a throwaway temp file, delegates, and maps the result
to a small stable report. Credentials are skipped on purpose: a missing
user API key is handled by the agent-model resolver / an honest caveat,
never as a "fixable" validation error the loop would chase.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lfx.cli.validation.core import LEVEL_REQUIRED_INPUTS, validate_flow_file
from lfx.log.logger import logger


@dataclass(frozen=True)
class FlowValidationReport:
    """Deterministic Tier-1 outcome for a built flow."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _format_issue(node_name: str | None, message: str) -> str:
    return f"{node_name}: {message}" if node_name else message


def _unknown_component_errors(flow: dict[str, Any]) -> list[str]:
    """Flag node types absent from the AGENTIC registry.

    The reused CLI validator's component-existence check loads a
    different (and here unavailable) registry and is unaware of the
    user's overlay components. The authoritative registry is the one the
    assistant builds with — check against that. Degrades to no errors if
    the registry can't be loaded (defensive: never false-positive).
    """
    try:
        from lfx.mcp.flow_builder_tools import _load_registry_user_aware

        known = set(_load_registry_user_aware().keys())
    except Exception as exc:  # noqa: BLE001 — registry unavailable → skip, don't false-flag
        logger.warning("assistant.flow_validation.registry_unavailable: %s", exc)
        return []
    if not known:
        return []

    errors: list[str] = []
    for node in flow.get("data", {}).get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        ctype = (node.get("data") or {}).get("type")
        if ctype and ctype not in known:
            node_id = node.get("id") or (node.get("data") or {}).get("id") or "?"
            errors.append(f"{node_id}: Unknown component type '{ctype}'. It is not in the registry.")
    return errors


def validate_flow_spec(flow: dict[str, Any]) -> FlowValidationReport:
    """Statically validate a flow dict; never raises.

    Args:
        flow: The working-flow dict to validate.

    Returns:
        A :class:`FlowValidationReport`. ``ok`` is False when the reused
        validator reports any error-severity issue (or the flow can't be
        serialized); warnings never flip ``ok``.
    """
    try:
        serialized = json.dumps(flow)
    except (TypeError, ValueError) as exc:
        return FlowValidationReport(ok=False, errors=[f"Flow is not serializable: {exc}"])

    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115 — explicit lifetime (must exist during validate)
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    tmp_path = Path(tmp.name)
    try:
        tmp.write(serialized)
        tmp.close()
        result = validate_flow_file(
            tmp_path,
            level=LEVEL_REQUIRED_INPUTS,
            skip_credentials=True,
        )
    except Exception as exc:  # noqa: BLE001 — validation must never break the build
        logger.warning("assistant.flow_validation.tier1_failed: %s", exc)
        return FlowValidationReport(ok=False, errors=[f"Static validation could not run: {exc}"])
    finally:
        tmp_path.unlink(missing_ok=True)

    errors = [_format_issue(i.node_name, i.message) for i in result.errors]
    errors.extend(_unknown_component_errors(flow))
    return FlowValidationReport(
        ok=not errors,
        errors=errors,
        warnings=[i.message for i in result.warnings],
    )
