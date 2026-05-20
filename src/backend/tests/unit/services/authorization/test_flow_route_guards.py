"""Regression tests asserting every flow CRUD route is wired through ensure_flow_permission.

These are intentionally source-level checks rather than full FastAPI integration tests:
the helper-level behavior is covered exhaustively in ``test_utils.py``; what these
tests prevent is the route being silently dropped or reverting to a bare action
string. A future PR will add a full app fixture + stub enterprise plugin.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_FLOWS_FILE = Path(__file__).resolve().parents[4] / "base" / "langflow" / "api" / "v1" / "flows.py"


def _parse_flow_routes() -> dict[str, ast.AsyncFunctionDef]:
    """Return the AST of every async route handler in flows.py keyed by function name."""
    tree = ast.parse(_FLOWS_FILE.read_text())
    return {node.name: node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)}


def _ensure_flow_permission_calls(func: ast.AsyncFunctionDef) -> list[ast.Call]:
    """Return every ensure_flow_permission(...) call within the function body."""
    calls: list[ast.Call] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        is_match = (isinstance(target, ast.Name) and target.id == "ensure_flow_permission") or (
            isinstance(target, ast.Attribute) and target.attr == "ensure_flow_permission"
        )
        if is_match:
            calls.append(node)
    return calls


def _action_arg(call: ast.Call) -> str | None:
    """Extract the action argument (positional[1]) as the dotted name like 'FlowAction.READ'."""
    if len(call.args) < 2:
        return None
    arg = call.args[1]
    if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
        return f"{arg.value.id}.{arg.attr}"
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


@pytest.fixture(scope="module")
def routes() -> dict[str, ast.AsyncFunctionDef]:
    return _parse_flow_routes()


@pytest.mark.parametrize(
    ("func_name", "expected_action"),
    [
        ("create_flow", "FlowAction.CREATE"),
        ("read_flow", "FlowAction.READ"),
        ("update_flow", "FlowAction.WRITE"),
        ("delete_flow", "FlowAction.DELETE"),
        ("create_flows", "FlowAction.CREATE"),
        ("upload_file", "FlowAction.CREATE"),
    ],
)
def test_single_guard_route_uses_enum_action(routes, func_name, expected_action):
    """Single-call guard routes call ensure_flow_permission once with the right FlowAction."""
    func = routes[func_name]
    calls = _ensure_flow_permission_calls(func)
    assert calls, f"{func_name} has no ensure_flow_permission call"
    actions = {_action_arg(c) for c in calls}
    assert expected_action in actions, f"{func_name} actions={actions}, expected {expected_action}"


def test_upsert_flow_guards_both_create_and_write(routes):
    """upsert_flow has two guard branches — WRITE for existing flows, CREATE for new ones."""
    func = routes["upsert_flow"]
    actions = {_action_arg(c) for c in _ensure_flow_permission_calls(func)}
    assert "FlowAction.WRITE" in actions
    assert "FlowAction.CREATE" in actions


def test_delete_multiple_flows_guards_each_flow(routes):
    """Bulk delete iterates and calls ensure_flow_permission per loaded flow."""
    func = routes["delete_multiple_flows"]
    actions = {_action_arg(c) for c in _ensure_flow_permission_calls(func)}
    assert actions == {"FlowAction.DELETE"}


def test_download_multiple_file_guards_each_flow(routes):
    """Bulk download iterates and calls ensure_flow_permission per loaded flow."""
    func = routes["download_multiple_file"]
    actions = {_action_arg(c) for c in _ensure_flow_permission_calls(func)}
    assert actions == {"FlowAction.READ"}


def _kwarg_source(call: ast.Call, kw_name: str) -> str | None:
    """Return the unparsed source of a keyword arg, or None if absent."""
    for kw in call.keywords:
        if kw.arg == kw_name:
            return ast.unparse(kw.value)
    return None


def _is_inside_for_loop_over(func: ast.AsyncFunctionDef, call: ast.Call, iter_attr: str) -> bool:
    """Return True if *call* is inside a `for ... in <something>.<iter_attr>` loop in *func*."""
    for node in ast.walk(func):
        if not isinstance(node, ast.For):
            continue
        iter_src = ast.unparse(node.iter)
        if not iter_src.endswith(f".{iter_attr}"):
            continue
        for sub in ast.walk(node):
            if sub is call:
                return True
    return False


def test_create_flows_guards_each_flow_with_its_destination(routes):
    """POST /batch/ must call ensure_flow_permission per flow with that flow's own scope.

    A caller-supplied batch can target multiple workspace_id/folder_id values, so a
    single coarse check at the route boundary would let unauthorized destinations slip
    through. Each call must pass ``workspace_id=flow.workspace_id`` and
    ``folder_id=flow.folder_id`` and live inside an iteration over ``flow_list.flows``.
    """
    func = routes["create_flows"]
    calls = _ensure_flow_permission_calls(func)
    assert calls, "create_flows lost its ensure_flow_permission call"
    assert {_action_arg(c) for c in calls} == {"FlowAction.CREATE"}
    scoped_calls = [
        c
        for c in calls
        if _kwarg_source(c, "workspace_id") == "flow.workspace_id"
        and _kwarg_source(c, "folder_id") == "flow.folder_id"
        and _is_inside_for_loop_over(func, c, "flows")
    ]
    assert scoped_calls, (
        "create_flows must call ensure_flow_permission inside a per-flow loop with flow.workspace_id and flow.folder_id"
    )


def test_upload_file_guards_each_flow_with_effective_destination(routes):
    """POST /upload/ adds a per-flow check after parsing.

    `_upsert_flow_list` lets the query ``folder_id`` override each flow's folder_id but
    preserves each flow's workspace_id, so the per-flow check must use
    ``workspace_id=flow.workspace_id`` and live inside a loop over ``flow_list.flows``.
    """
    func = routes["upload_file"]
    calls = _ensure_flow_permission_calls(func)
    assert calls, "upload_file lost its ensure_flow_permission call"
    assert "FlowAction.CREATE" in {_action_arg(c) for c in calls}
    scoped_calls = [
        c
        for c in calls
        if _kwarg_source(c, "workspace_id") == "flow.workspace_id" and _is_inside_for_loop_over(func, c, "flows")
    ]
    assert scoped_calls, "upload_file must call ensure_flow_permission inside a per-flow loop with flow.workspace_id"


def _has_destination_check(
    func: ast.AsyncFunctionDef,
    *,
    target_workspace_kw: str,
    target_folder_kw: str,
) -> bool:
    """Return True if *func* has a WRITE ensure_flow_permission call with the destination kwargs."""
    for call in _ensure_flow_permission_calls(func):
        if _action_arg(call) != "FlowAction.WRITE":
            continue
        ws = _kwarg_source(call, "workspace_id")
        fld = _kwarg_source(call, "folder_id")
        if ws == target_workspace_kw and fld == target_folder_kw:
            return True
    return False


def test_update_flow_authorizes_destination_on_move(routes):
    """PATCH /flows/{flow_id} must authorize the destination on workspace/folder change.

    Without this, a caller could write to a flow in scope A and move it into
    scope B even when they lack permission to write at B (e.g., share-based
    access in Phase 3 or workspace-scoped roles in enterprise).
    """
    func = routes["update_flow"]
    assert _has_destination_check(
        func,
        target_workspace_kw="target_workspace_id",
        target_folder_kw="target_folder_id",
    ), "update_flow must authorize WRITE at target_workspace_id/target_folder_id when moving"


def test_upsert_flow_update_branch_authorizes_destination_on_move(routes):
    """PUT /flows/{flow_id} (update branch) must authorize the destination on move."""
    func = routes["upsert_flow"]
    assert _has_destination_check(
        func,
        target_workspace_kw="target_workspace_id",
        target_folder_kw="target_folder_id",
    ), "upsert_flow must authorize WRITE at target_workspace_id/target_folder_id when moving"


def test_no_bare_string_actions_remain(routes):
    """No flow-route guard should use a bare string action — the enum is now canonical."""
    offenders: list[str] = []
    for name, func in routes.items():
        for call in _ensure_flow_permission_calls(func):
            arg = _action_arg(call)
            if arg is not None and not arg.startswith("FlowAction."):
                offenders.append(f"{name}:{arg}")
    assert offenders == [], f"bare-string actions found: {offenders}"


def test_read_public_flow_remains_unguarded(routes):
    """The /public_flow/{id} endpoint must not call ensure_flow_permission — public means public."""
    func = routes["read_public_flow"]
    assert _ensure_flow_permission_calls(func) == []


def test_read_flows_list_unchanged_in_this_pr(routes):
    """GET /flows/ list endpoint still has no per-item guard — filter helper lands in a follow-up PR."""
    func = routes["read_flows"]
    assert _ensure_flow_permission_calls(func) == []
