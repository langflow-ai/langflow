"""Source-level tests that flow routes call ensure_flow_permission."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_API_V1 = Path(__file__).resolve().parents[4] / "base" / "langflow" / "api" / "v1"
_FLOWS_FILE = _API_V1 / "flows.py"
_CHAT_FILE = _API_V1 / "chat.py"
_ENDPOINTS_FILE = _API_V1 / "endpoints.py"
_PROJECTS_FILE = _API_V1 / "projects.py"


def _parse_async_funcs(path: Path) -> dict[str, ast.AsyncFunctionDef]:
    """Return the AST of every async function in *path* keyed by function name."""
    tree = ast.parse(path.read_text())
    return {node.name: node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)}


def _parse_flow_routes() -> dict[str, ast.AsyncFunctionDef]:
    """Return the AST of every async route handler in flows.py keyed by function name."""
    return _parse_async_funcs(_FLOWS_FILE)


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


def _uses_authorized_flow_dependency(func: ast.AsyncFunctionDef, alias: str) -> bool:
    """Return True if *func* declares an authorized-flow dependency alias in its signature."""
    for arg in func.args.args + func.args.kwonlyargs:
        if arg.annotation is None:
            continue
        ann = ast.unparse(arg.annotation)
        if alias in ann:
            return True
    for node in ast.walk(func):
        if isinstance(node, ast.AnnAssign) and node.annotation is not None and alias in ast.unparse(node.annotation):
            return True
    return False


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
    if calls:
        actions = {_action_arg(c) for c in calls}
        assert expected_action in actions, f"{func_name} actions={actions}, expected {expected_action}"
        return

    # Routes migrated to FastAPI dependencies declare protection in the signature.
    alias_by_action = {
        "FlowAction.CREATE": "RequireFlowCreate",
        "FlowAction.READ": "AuthorizedReadFlow",
        "FlowAction.WRITE": "AuthorizedWriteFlow",
        "FlowAction.DELETE": "AuthorizedDeleteFlow",
    }
    alias = alias_by_action.get(expected_action)
    assert alias is not None
    assert _uses_authorized_flow_dependency(func, alias), (
        f"{func_name} has no ensure_flow_permission call or {alias} dependency"
    )


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
    access in Phase 3 or workspace-scoped roles in plugin).
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


def test_get_note_translations_is_owner_scoped_and_guarded(routes):
    """`GET /flows/{flow_id}/note_translations` must authorize READ via dependency or inline guard."""
    func = routes["get_note_translations"]
    calls = _ensure_flow_permission_calls(func)
    if calls:
        actions = {_action_arg(c) for c in calls}
        assert "FlowAction.READ" in actions, f"expected FlowAction.READ, got {actions}"
        read_flow_calls = [
            node
            for node in ast.walk(func)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "_read_flow")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "_read_flow")
            )
        ]
        assert read_flow_calls, "get_note_translations must fetch the flow via _read_flow (owner-scoped)"
        return

    assert any(_uses_authorized_flow_dependency(func, alias) for alias in ("AuthorizedReadFlow",)), (
        "get_note_translations must declare an authorized read dependency or call ensure_flow_permission"
    )


def test_read_flows_list_uses_filter_visible_resources(routes):
    """GET /flows/ applies filter_visible_resources on BOTH the get_all and paginated paths.

    The list helper drops items the user can't read. In OSS pass-through it
    returns the input unchanged; the authorization plugin uses batch_enforce to
    honor role + share grants. Per-item ensure_flow_permission is intentionally
    NOT used here — filtering is the right primitive for list endpoints.

    Asserting **two** filter_visible_resources calls catches the earlier gap
    where only the get_all branch was filtered and the paginated branch
    (``get_all=False``) returned the raw ``apaginate`` result unfiltered.
    """
    func = routes["read_flows"]
    # No per-item ensure_flow_permission (would 403 on the first unauthorized item).
    assert _ensure_flow_permission_calls(func) == []

    filter_calls = [
        node
        for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "filter_visible_resources")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "filter_visible_resources")
        )
    ]
    assert len(filter_calls) == 2, (
        f"expected two filter_visible_resources calls (get_all + paginated branches), got {len(filter_calls)}"
    )


# ----------------------------------------------------------------------------- #
# Phase B: execute-action guards on build/run/webhook surfaces
# ----------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("module_path", "func_name"),
    [
        (_CHAT_FILE, "build_flow"),
        # Deprecated but still routed — guarded with EXECUTE just like the
        # supported build_flow. ``build_graph_from_db`` does a raw
        # ``session.get(Flow, flow_id)`` with no owner filter, so the route
        # handler must enforce ownership itself.
        (_CHAT_FILE, "retrieve_vertices_order"),
        (_CHAT_FILE, "build_vertex"),
        (_ENDPOINTS_FILE, "simplified_run_flow"),
        (_ENDPOINTS_FILE, "simplified_run_flow_session"),
        (_ENDPOINTS_FILE, "webhook_run_flow"),
        (_ENDPOINTS_FILE, "experimental_run_flow"),
    ],
)
def test_execute_surfaces_guard_with_flow_execute(module_path, func_name):
    """build/run/webhook handlers must call ensure_flow_permission(FlowAction.EXECUTE)."""
    funcs = _parse_async_funcs(module_path)
    assert func_name in funcs, f"{func_name} missing from {module_path.name}"
    calls = _ensure_flow_permission_calls(funcs[func_name])
    assert calls, f"{func_name} has no ensure_flow_permission call"
    actions = {_action_arg(c) for c in calls}
    assert "FlowAction.EXECUTE" in actions, f"{func_name} actions={actions}, expected FlowAction.EXECUTE"


def test_check_flow_user_permission_is_gone():
    """The standalone owner-only ``check_flow_user_permission`` helper has been removed.

    It duplicated the work that ``ensure_flow_permission`` now does at the
    route boundary, AND it would have rejected legitimate plugin execute
    grants on shared flows (a real bug under policy engine enforcement). The new
    contract is "every ``_run_flow_internal`` caller authorizes EXECUTE first";
    leaving a downstream owner-only check would silently re-introduce the
    regression on any future route that wires up the internal helper without
    calling ensure_flow_permission upstream.
    """
    funcs = _parse_async_funcs(_ENDPOINTS_FILE)
    assert "check_flow_user_permission" not in funcs, (
        "check_flow_user_permission should be removed; the route-level "
        "ensure_flow_permission(EXECUTE) is the only authorization gate now"
    )


# ----------------------------------------------------------------------------- #
# Phase B: project route guards
# ----------------------------------------------------------------------------- #


def _ensure_project_permission_calls(func: ast.AsyncFunctionDef) -> list[ast.Call]:
    """Return every ensure_project_permission(...) call within the function body."""
    calls: list[ast.Call] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        is_match = (isinstance(target, ast.Name) and target.id == "ensure_project_permission") or (
            isinstance(target, ast.Attribute) and target.attr == "ensure_project_permission"
        )
        if is_match:
            calls.append(node)
    return calls


@pytest.mark.parametrize(
    ("func_name", "expected_action"),
    [
        ("create_project", "ProjectAction.CREATE"),
        ("read_project", "ProjectAction.READ"),
        ("update_project", "ProjectAction.WRITE"),
        ("delete_project", "ProjectAction.DELETE"),
        ("download_file", "ProjectAction.READ"),
        ("upload_file", "ProjectAction.CREATE"),
    ],
)
def test_project_routes_guarded(func_name, expected_action):
    """Each project CRUD handler calls ensure_project_permission with the right ProjectAction."""
    funcs = _parse_async_funcs(_PROJECTS_FILE)
    assert func_name in funcs, f"{func_name} missing from projects.py"
    calls = _ensure_project_permission_calls(funcs[func_name])
    assert calls, f"{func_name} has no ensure_project_permission call"
    actions = {_action_arg(c) for c in calls}
    assert expected_action in actions, f"{func_name} actions={actions}, expected {expected_action}"
