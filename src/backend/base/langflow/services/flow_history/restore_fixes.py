"""Checking the fixes a client sends with a restore.

A restore whose revision breaks edge rules marked ``manual`` is
resent with fixes (see ops-history, "Repair"). The fixes are operations, and
each one must address a violation the restore would hit, in the way that
violation's client action allows:

- an edge whose handles are invalid or name nothing may be deleted, or
  deleted and added again with other handles;
- of the edges into an input that takes one, any may be deleted.

An edge never changes in place, so a handle rewrite is a ``delete_edges`` and
an ``add_edges`` of the same edge.

Anything else is an edit, which takes the save path.
"""

from __future__ import annotations

from typing import Annotated, Any

from lfx.services.flow_operations import (
    AddEdgesOp,
    DeleteEdgesOp,
    FlowOperationError,
    GraphViolationCode,
    Resolution,
    apply_flow_operations,
    find_graph_violations,
    resolution_of,
    values_equal,
)
from lfx.services.flow_operations.edge_rules import HANDLE_KEYS, read_handles
from pydantic import Field

from langflow.services.flow_history.errors import RestoreFixNotAllowedError

# One fix a restore takes: an edge delete, or an edge added back with other handles.
RestoreFix = Annotated[DeleteEdgesOp | AddEdgesOp, Field(discriminator="type")]
RESTORE_FIXES_DESCRIPTION = (
    "The client's fixes for a restore refused with manual violations: edge deletes, and edges added back "
    "with other handles, each addressing one of those violations, applied before the restored flow is saved."
)

_REWRITABLE = frozenset({GraphViolationCode.EDGE_HANDLE_INVALID, GraphViolationCode.EDGE_HANDLE_NOT_FOUND})


def apply_restore_fixes(
    revision: dict[str, Any], stored: dict[str, Any], fixes: list[DeleteEdgesOp | AddEdgesOp]
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
    revision: dict[str, Any], stored: dict[str, Any], fixes: list[DeleteEdgesOp | AddEdgesOp]
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

    deleted: set[str] = set()
    for fix in fixes:
        if isinstance(fix, DeleteEdgesOp):
            for edge_id in fix.ids:
                if edge_id not in deletable:
                    msg = f"edge {edge_id!r} breaks no edge rule the client may fix by deleting it"
                    raise RestoreFixNotAllowedError(msg)
            deleted.update(fix.ids)
            continue
        for edge in fix.edges:
            edge_id = edge.get("id")
            if edge_id not in rewritable:
                msg = f"edge {edge_id!r} has no handles the client may rewrite"
                raise RestoreFixNotAllowedError(msg)
            if edge_id not in deleted:
                msg = f"edge {edge_id!r}: a fix adds an edge only after it deletes it"
                raise RestoreFixNotAllowedError(msg)
            if not _only_handles_differ(by_id[edge_id], edge):
                msg = f"edge {edge_id!r}: a fix may only change the edge's handles"
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


def _only_handles_differ(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Return whether two versions of an edge differ only in their handles, in either form.

    An edge without a ``data`` object may gain one that holds only handles.
    """
    return values_equal(_without_handles(before), _without_handles(after))


def _without_handles(edge: dict[str, Any]) -> dict[str, Any]:
    """Return an edge without its handles, and without a ``data`` that is not an object or holds nothing else."""
    rest = {key: value for key, value in edge.items() if key not in HANDLE_KEYS}
    data = rest.pop("data", None)
    if isinstance(data, dict):
        data = {key: value for key, value in data.items() if key not in HANDLE_KEYS}
        if data:
            rest["data"] = data
    return rest
