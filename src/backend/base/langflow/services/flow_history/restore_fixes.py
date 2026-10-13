"""Checking the fixes a client sends with a restore.

A restore whose revision breaks edge rules marked ``manual`` is
resent with fixes (see ops-history, "Repair"). The fixes are operations, and
each one must address a violation the restore would hit, in the way that
violation's client action allows:

- an edge whose handles are invalid or name nothing may be deleted, or have
  its handles rewritten;
- of the edges into an input that takes one, any may be deleted.

Anything else is an edit, which takes the save path.
"""

from __future__ import annotations

from typing import Annotated, Any

from lfx.services.flow_operations import (
    DeleteEdgesOp,
    FlowOperationError,
    GraphViolationCode,
    Resolution,
    SetNodeFieldUpdate,
    UpdateEdgesOp,
    apply_flow_operations,
    find_graph_violations,
    resolution_of,
)
from lfx.services.flow_operations.edge_rules import HANDLE_KEYS, read_handles
from pydantic import Field

from langflow.services.flow_history.errors import RestoreFixNotAllowedError

# One fix a restore takes: an edge delete or a handle rewrite.
RestoreFix = Annotated[DeleteEdgesOp | UpdateEdgesOp, Field(discriminator="type")]
RESTORE_FIXES_DESCRIPTION = (
    "The client's fixes for a restore refused with manual violations: edge deletes and handle rewrites, "
    "each addressing one of those violations, applied before the restored flow is saved."
)

_REWRITABLE = frozenset({GraphViolationCode.EDGE_HANDLE_INVALID, GraphViolationCode.EDGE_HANDLE_NOT_FOUND})
_HANDLE_PATHS = frozenset({(key,) for key in HANDLE_KEYS} | {("data", key) for key in HANDLE_KEYS})


def apply_restore_fixes(
    revision: dict[str, Any], stored: dict[str, Any], fixes: list[DeleteEdgesOp | UpdateEdgesOp]
) -> dict[str, Any]:
    """Return ``revision`` with ``fixes`` applied, after checking each one (``check_restore_fixes``).

    Raises ``RestoreFixNotAllowedError`` for a fix that addresses no violation,
    or that the engine cannot apply, with the engine's code.
    """
    check_restore_fixes(revision, stored, fixes)
    try:
        return apply_flow_operations(revision, list(fixes)).flow_data
    except FlowOperationError as exc:
        msg = f"A fix cannot be applied: {exc}"
        raise RestoreFixNotAllowedError(msg, code=exc.code) from exc


def check_restore_fixes(
    revision: dict[str, Any], stored: dict[str, Any], fixes: list[DeleteEdgesOp | UpdateEdgesOp]
) -> None:
    """Raise ``RestoreFixNotAllowedError`` unless every fix addresses a violation restoring ``revision`` would hit.

    The violations are the ones the save makes: ``revision`` checked against
    the ``stored`` flow it replaces.
    """
    edges = revision["edges"]
    by_id = {edge["id"]: edge for edge in edges}
    deletable: set[str] = set()
    rewritable: set[str] = set()
    for violation in find_graph_violations(revision, base=stored):
        if violation.edge_id is None or resolution_of(violation.code) is not Resolution.MANUAL:
            continue
        deletable.add(violation.edge_id)
        if violation.code in _REWRITABLE:
            rewritable.add(violation.edge_id)
        elif violation.code is GraphViolationCode.EDGE_TARGET_OCCUPIED:
            deletable |= _edges_into_the_same_input(edges, by_id[violation.edge_id])

    for fix in fixes:
        if isinstance(fix, DeleteEdgesOp):
            for edge_id in fix.ids:
                if edge_id not in deletable:
                    msg = f"edge {edge_id!r} breaks no edge rule the client may fix by deleting it"
                    raise RestoreFixNotAllowedError(msg)
            continue
        for update in fix.updates:
            if update.id not in rewritable:
                msg = f"edge {update.id!r} has no handles the client may rewrite"
                raise RestoreFixNotAllowedError(msg)
            if not _rewrites_handles(update, by_id[update.id]):
                msg = f"edge {update.id!r}: a fix may only set the edge's handles"
                raise RestoreFixNotAllowedError(msg)


def _edges_into_the_same_input(edges: list[dict[str, Any]], edge: dict[str, Any]) -> set[str]:
    """Return the edges into the input ``edge`` takes, whose handles are valid since it is occupied."""
    taken = read_handles(edge).input
    same: set[str] = set()
    for other in edges:
        if other["target"] != edge["target"]:
            continue
        try:
            if read_handles(other).input == taken:
                same.add(other["id"])
        except FlowOperationError:
            # An edge with broken handles takes no input; its own violation says what may fix it.
            continue
    return same


def _rewrites_handles(update: Any, edge: dict[str, Any]) -> bool:
    """Return whether ``update`` sets one of the edge's handles, or its whole ``data`` when it has none."""
    if not isinstance(update, SetNodeFieldUpdate):
        return False
    path = tuple(update.path)
    if path in _HANDLE_PATHS:
        return True
    return (
        path == ("data",)
        and not isinstance(edge.get("data"), dict)
        and isinstance(update.value, dict)
        and set(update.value) <= set(HANDLE_KEYS)
    )
