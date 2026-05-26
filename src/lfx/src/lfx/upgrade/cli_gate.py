"""Shared ``--upgrade-flow`` gate for the ``run`` and ``serve`` CLI paths.

Both ``lfx run`` and ``lfx serve`` accept ``--upgrade-flow`` with identical semantics:

  - ``check``: refuse to run if any component is outdated or blocked.
  - ``safe``:  auto-apply safe upgrades, but abort on breaking or blocked components.

This module is the single source of truth for that behavior so the two entry points can
never diverge. Callers translate :class:`UpgradeFlowError` into their own error channel
(``RunError`` for ``run_flow``; ``typer.Exit`` for ``serve_command``).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from lfx.upgrade.applier import apply_safe_upgrades
from lfx.upgrade.checker import build_registry_lookup, check_flow_compatibility

if TYPE_CHECKING:
    from collections.abc import Mapping


class UpgradeFlowMode(str, Enum):
    """Accepted values for ``--upgrade-flow``.

    Subclasses ``str`` so existing string comparisons and call sites that pass the literal
    ``"check"`` / ``"safe"`` continue to work unchanged.
    """

    CHECK = "check"
    SAFE = "safe"


class UpgradeFlowError(Exception):
    """Raised when the ``--upgrade-flow`` gate aborts (incompatible/blocked/breaking/unknown)."""


def apply_upgrade_gate(
    flow_dict: dict,
    all_types_dict: Mapping[str, Any],
    mode: str,
) -> tuple[dict, int]:
    """Run the ``--upgrade-flow`` gate against ``flow_dict``.

    Returns ``(flow_dict, applied_count)`` where ``flow_dict`` is the upgraded graph in ``safe``
    mode (or the input unchanged in ``check`` mode / when nothing was applied), and
    ``applied_count`` is the number of safe upgrades written.

    Raises:
        UpgradeFlowError: if ``check`` finds anything not ``ok``, if ``safe`` hits a breaking
            or blocked component, or if ``mode`` is not a recognized value.
    """
    # Validate the mode before any registry work so a typo fails fast and cheaply.
    if mode not in (UpgradeFlowMode.CHECK, UpgradeFlowMode.SAFE):
        msg = f"Unknown --upgrade-flow value '{mode}'. Use 'safe' or 'check'."
        raise UpgradeFlowError(msg)

    # Build the registry lookup once and reuse it for the check (and the apply, in safe mode).
    registry = build_registry_lookup(all_types_dict)
    report = check_flow_compatibility(flow_dict, all_types_dict, registry=registry)

    if mode == UpgradeFlowMode.CHECK:
        if not report.is_clean:
            names = ", ".join(f"{n.display_name} ({n.status})" for n in report.nodes if n.status != "ok")
            msg = f"flow has incompatible components (--upgrade-flow=check): {names}"
            raise UpgradeFlowError(msg)
        return flow_dict, 0

    # mode is SAFE.
    if report.has_blocked or report.has_breaking:
        names = ", ".join(
            f"{n.display_name} ({n.status})" for n in report.nodes if n.status in ("blocked", "outdated_breaking")
        )
        msg = f"flow has components that cannot be auto-upgraded: {names}"
        raise UpgradeFlowError(msg)
    if report.has_safe_updates:
        return apply_safe_upgrades(flow_dict, all_types_dict, report, return_count=True, registry=registry)
    return flow_dict, 0
