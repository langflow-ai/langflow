"""Source-level regression tests for authorization route guard wiring."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_API_V1 = Path(__file__).resolve().parents[4] / "base" / "langflow" / "api" / "v1"
_FLOWS_FILE = _API_V1 / "flows.py"
_PROJECTS_FILE = _API_V1 / "projects.py"
_DEPLOYMENTS_FILE = _API_V1 / "deployments.py"
_HELPERS_FLOW = Path(__file__).resolve().parents[4] / "base" / "langflow" / "helpers" / "flow.py"


def _parse_async_funcs(path: Path) -> dict[str, ast.AsyncFunctionDef]:
    tree = ast.parse(path.read_text())
    return {node.name: node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)}


def _calls(func: ast.AsyncFunctionDef, name: str) -> list[ast.Call]:
    out: list[ast.Call] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        is_named = isinstance(target, ast.Name) and target.id == name
        is_attr = isinstance(target, ast.Attribute) and target.attr == name
        if is_named or is_attr:
            out.append(node)
    return out


def _has_keyword(call: ast.Call, name: str) -> bool:
    return any(kw.arg == name for kw in call.keywords)


@pytest.fixture(scope="module")
def flows_routes() -> dict[str, ast.AsyncFunctionDef]:
    return _parse_async_funcs(_FLOWS_FILE)


@pytest.fixture(scope="module")
def projects_routes() -> dict[str, ast.AsyncFunctionDef]:
    return _parse_async_funcs(_PROJECTS_FILE)


@pytest.fixture(scope="module")
def deployments_routes() -> dict[str, ast.AsyncFunctionDef]:
    return _parse_async_funcs(_DEPLOYMENTS_FILE)


@pytest.fixture(scope="module")
def helpers_funcs() -> dict[str, ast.AsyncFunctionDef]:
    return _parse_async_funcs(_HELPERS_FLOW)


def test_read_flows_paginated_branch_passes_owner_extractor(flows_routes):
    """The paginated filter_visible_resources call must pass owner_extractor.

    Both branches of read_flows (``get_all=True`` and pagination) must give
    the enforcer the same hint about which flows are owner-owned. Omitting it
    on the paginated branch lets an authorization plugin without an explicit
    owner-allow policy hide the caller's own flows when paginating.
    """
    func = flows_routes["read_flows"]
    fvr_calls = _calls(func, "filter_visible_resources")
    assert len(fvr_calls) >= 2, "read_flows should call filter_visible_resources on both branches"
    for call in fvr_calls:
        assert _has_keyword(call, "owner_extractor"), (
            "Every filter_visible_resources call in read_flows must pass owner_extractor "
            "so the enforcer short-circuits on owner-allow"
        )


def test_upsert_flow_consults_cross_user_fetch_capability(flows_routes):
    """upsert_flow must not unconditionally raise 404 for non-owners.

    With an authorization plugin registered, a valid WRITE share grant must be
    honored. The current shape gates the hardcoded ownership floor on
    ``supports_cross_user_fetch() and is_enabled()``.
    """
    func = flows_routes["upsert_flow"]
    src = ast.unparse(func)
    assert "supports_cross_user_fetch" in src, "upsert_flow must consult cross-user-fetch capability"
    assert "is_enabled" in src, "upsert_flow must consult is_enabled before the OSS floor"


def test_upsert_flow_wraps_ensure_in_deny_to_404(flows_routes):
    """upsert_flow must convert ensure_flow_permission 403 to 404 for UUID privacy."""
    func = flows_routes["upsert_flow"]
    src = ast.unparse(func)
    assert "deny_to_404" in src, "upsert_flow must wrap ensure_flow_permission with deny_to_404"


def test_delete_multiple_flows_does_not_unconditionally_prescope(flows_routes):
    """Bulk delete must not unconditionally filter by Flow.user_id == user.id.

    The pre-scope is now gated on whether the registered service supports
    cross-user fetch — otherwise valid share DELETE grants are silently
    dropped from the working set.
    """
    func = flows_routes["delete_multiple_flows"]
    src = ast.unparse(func)
    assert "supports_cross_user_fetch" in src, (
        "delete_multiple_flows must gate the owner pre-scope on cross-user-fetch capability"
    )


def test_download_multiple_file_does_not_unconditionally_prescope(flows_routes):
    """Same as above for the bulk download endpoint."""
    func = flows_routes["download_multiple_file"]
    src = ast.unparse(func)
    assert "supports_cross_user_fetch" in src, (
        "download_multiple_file must gate the owner pre-scope on cross-user-fetch capability"
    )
    assert "deny_to_404" in src, (
        "download_multiple_file must convert ensure_flow_permission 403 to 404 for UUID privacy"
    )


def test_read_project_paginated_branch_filters_via_filter_visible_resources(projects_routes):
    """The paginated branch of ``read_project`` must apply per-flow authz too.

    A project READ grant must not bypass finer-grained per-flow policy just
    because the caller asked for pagination. Both the non-paginated and
    paginated branches must call ``filter_visible_resources`` when the
    project is reached via a share grant (``treat_as_shared``); otherwise
    shared-project reads behave differently depending on page/size.
    """
    func = projects_routes["read_project"]
    fvr_calls = _calls(func, "filter_visible_resources")
    assert len(fvr_calls) >= 2, (
        "read_project must call filter_visible_resources on both the paginated "
        "and non-paginated shared-project branches"
    )


def test_read_flows_wires_db_layer_prefilter(flows_routes):
    """read_flows must call ``visible_id_prefilter`` so an EE plugin can prefilter at the DB.

    Without this the plugin's ``list_visible_resource_ids`` override has no
    effect on the listing — every candidate row is fetched and filtered in
    memory, defeating the hook at large-tenant scale.
    """
    func = flows_routes["read_flows"]
    assert _calls(func, "visible_id_prefilter"), "read_flows must consult visible_id_prefilter"


def test_read_projects_wires_db_layer_prefilter(projects_routes):
    """read_projects must call ``visible_id_prefilter`` (DB-layer prefilter)."""
    func = projects_routes["read_projects"]
    assert _calls(func, "visible_id_prefilter"), "read_projects must consult visible_id_prefilter"


def test_read_project_wires_db_layer_prefilter(projects_routes):
    """read_project (flows-in-project) must call ``visible_id_prefilter`` too."""
    func = projects_routes["read_project"]
    assert _calls(func, "visible_id_prefilter"), "read_project must consult visible_id_prefilter"


def test_list_deployments_threads_prefilter_into_synced_query(deployments_routes):
    """list_deployments must consult the prefilter AND thread it into the synced query.

    Passing ``allowed_ids`` into ``list_deployments_synced`` is what pushes the
    prefilter down to both the page query and its count, so pagination totals
    reflect the constraint instead of overcounting denied rows.
    """
    func = deployments_routes["list_deployments"]
    assert _calls(func, "visible_id_prefilter"), "list_deployments must consult visible_id_prefilter"
    synced_calls = _calls(func, "list_deployments_synced")
    assert synced_calls, "list_deployments must call list_deployments_synced"
    assert any(_has_keyword(call, "allowed_ids") for call in synced_calls), (
        "list_deployments must thread allowed_ids into list_deployments_synced so the "
        "page query and its total share the prefilter"
    )


def test_list_deployments_relaxes_provider_gate_on_prefilter(deployments_routes):
    """list_deployments must not unconditionally apply the owner-scoped provider gate.

    A shared deployment lives under its *owner's* provider account, so the strict
    ``get_owned_provider_account_or_404`` 404s a cross-user reader before the
    ``(owner ⊕ visible)`` prefilter union can surface the row. When
    ``visible_id_prefilter`` returns a concrete list, the handler must resolve the
    provider account by id alone (``get_shared_listing_provider_account_or_404``)
    so ``allowed_ids`` can actually widen cross-user shared listing — while the
    OSS / no-plugin path keeps the strict owner gate.
    """
    func = deployments_routes["list_deployments"]
    src = ast.unparse(func)
    assert _calls(func, "get_shared_listing_provider_account_or_404"), (
        "list_deployments must resolve the provider account by id alone on the "
        "prefilter path so shared deployments under another user's provider "
        "account are listable"
    )
    assert "get_owned_provider_account_or_404" in src, (
        "list_deployments must keep the strict owner gate for the OSS / no-plugin path"
    )


def test_load_flow_calls_ensure_flow_permission(helpers_funcs):
    """load_flow (component-reachable graph loader) must authorize EXECUTE.

    Reachable from custom components, sub-flow runners, and ``run_flow``.
    Without this guard, a caller can pass an arbitrary flow_id and pull
    another user's flow definition (prompts, tools, embedded credentials).
    """
    func = helpers_funcs["load_flow"]
    calls = _calls(func, "ensure_flow_permission")
    if calls:
        saw_execute = False
        for call in calls:
            if len(call.args) >= 2:
                arg = call.args[1]
                if isinstance(arg, ast.Attribute) and arg.attr == "EXECUTE":
                    saw_execute = True
        assert saw_execute, "load_flow must authorize FlowAction.EXECUTE"
        return

    requires_calls = _calls(func, "requires_flow_permission")
    assert requires_calls, "load_flow must use requires_flow_permission or ensure_flow_permission"
    saw_execute = False
    for call in requires_calls:
        if call.args and isinstance(call.args[0], ast.Attribute) and call.args[0].attr == "EXECUTE":
            saw_execute = True
    assert saw_execute, "load_flow must authorize FlowAction.EXECUTE via decorator"
