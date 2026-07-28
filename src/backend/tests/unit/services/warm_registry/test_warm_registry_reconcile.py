"""DB-backed tests for the warm registry: reconcile, real graph build, host success.

Unlike ``test_warm_registry.py`` (hermetic, ``_build`` stubbed), these use the
``client`` fixture to boot a real service stack + test DB, insert real ``Flow``
rows, and drive the ACTUAL ``warm_all`` / ``warm_one`` / ``reconcile_once`` /
``reconcile_loop`` against the ``flow`` table — building real ``Graph`` templates
and serving them through ``WarmWorkflowHost.get_flow``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import langflow
import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope
from langflow.services.warm_registry import reconcile as reconcile_mod
from langflow.services.warm_registry import service as service_mod
from langflow.services.warm_registry.reconcile import reconcile_loop, reconcile_once, warm_all, warm_one
from langflow.services.warm_registry.service import WarmGraphRegistry, get_warm_registry
from sqlmodel import delete, select


@pytest.fixture
def clean_registry():
    """Reset the process-local singleton around each test so state never leaks."""
    service_mod._warm_registry = None
    yield
    service_mod._warm_registry = None


async def _insert_flow(name: str, data: dict, user_id, *, endpoint_name: str | None = None) -> str:
    async with session_scope() as session:
        flow = Flow(name=name, data=data, user_id=user_id, endpoint_name=endpoint_name)
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        return str(flow.id)


async def _clear_flows() -> None:
    async with session_scope() as session:
        await session.exec(delete(Flow))


async def _touch_flow(flow_id: str, new_name: str) -> None:
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))).first()
        flow.name = new_name
        flow.updated_at = datetime.now(timezone.utc)
        session.add(flow)


async def _delete_flow(flow_id: str) -> None:
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))).first()
        await session.delete(flow)


_STARTERS = Path(langflow.__file__).parent / "initial_setup" / "starter_projects"


@pytest.fixture
def basic_data() -> dict:
    # A current, buildable starter project (basic_example.json uses legacy
    # components that no longer build). Same flow the manual demo exercises.
    return json.loads((_STARTERS / "Basic Prompting.json").read_text(encoding="utf-8"))["data"]


async def test_warm_all_builds_real_graph(client, active_user, basic_data, clean_registry):  # noqa: ARG001
    """warm_all() queries the flow table and builds a real Graph template."""
    await _clear_flows()
    flow_id = await _insert_flow("warm-all", basic_data, active_user.id)

    await warm_all()

    reg = get_warm_registry()
    hit = reg.get(flow_id)
    assert hit is not None
    template, version = hit
    # A real built Graph, not a stub.
    assert type(template).__name__ == "Graph"
    assert len(template.vertices) > 0
    # version marker is the flow's updated_at isoformat.
    assert version  # non-empty


async def test_warm_all_skips_flows_without_data(client, active_user, clean_registry):  # noqa: ARG001
    await _clear_flows()
    await _insert_flow("no-data", {}, active_user.id)

    await warm_all()

    assert len(get_warm_registry()) == 0


async def test_warm_one_by_uuid_and_endpoint_name(client, active_user, basic_data, clean_registry):  # noqa: ARG001
    await _clear_flows()
    flow_id = await _insert_flow("by-name", basic_data, active_user.id, endpoint_name="my-endpoint")

    # Lookup by UUID caches under the canonical id.
    hit = await warm_one(flow_id)
    assert hit is not None
    assert get_warm_registry().get(flow_id) is not None

    # A fresh registry: lookup by endpoint name resolves and caches under the UUID.
    service_mod._warm_registry = None
    hit_by_name = await warm_one("my-endpoint")
    assert hit_by_name is not None
    assert get_warm_registry().get(flow_id) is not None  # stored under canonical UUID


async def test_warm_one_missing_returns_none(client, clean_registry):  # noqa: ARG001
    assert await warm_one(str(UUID(int=0))) is None
    assert await warm_one("does-not-exist") is None


async def test_reconcile_adds_new_flow(client, active_user, basic_data, clean_registry):  # noqa: ARG001
    await _clear_flows()
    await warm_all()
    assert len(get_warm_registry()) == 0

    flow_id = await _insert_flow("added-later", basic_data, active_user.id)
    await reconcile_once()

    assert get_warm_registry().get(flow_id) is not None


async def test_reconcile_rebuilds_changed_flow(client, active_user, basic_data, clean_registry):  # noqa: ARG001
    await _clear_flows()
    flow_id = await _insert_flow("v1", basic_data, active_user.id)
    await warm_all()
    version_before = get_warm_registry().version_of(flow_id)

    await _touch_flow(flow_id, "v2")
    await reconcile_once()

    version_after = get_warm_registry().version_of(flow_id)
    assert version_after != version_before


async def test_reconcile_evicts_deleted_flow(client, active_user, basic_data, clean_registry):  # noqa: ARG001
    await _clear_flows()
    keep_id = await _insert_flow("keep", basic_data, active_user.id)
    drop_id = await _insert_flow("drop", basic_data, active_user.id)
    await warm_all()
    assert len(get_warm_registry()) == 2

    await _delete_flow(drop_id)
    await reconcile_once()

    reg = get_warm_registry()
    assert reg.get(drop_id) is None
    assert reg.get(keep_id) is not None


async def test_reconcile_no_changes_is_stable(client, active_user, basic_data, clean_registry):  # noqa: ARG001
    await _clear_flows()
    await _insert_flow("stable", basic_data, active_user.id)
    await warm_all()
    ids_before = get_warm_registry().active_ids()

    await reconcile_once()

    assert get_warm_registry().active_ids() == ids_before


async def test_reconcile_fail_safe_keeps_registry_on_db_error(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
    monkeypatch,
):
    """A failing manifest query must NOT mass-evict the warm registry."""
    await _clear_flows()
    flow_id = await _insert_flow("resident", basic_data, active_user.id)
    await warm_all()
    assert get_warm_registry().get(flow_id) is not None

    monkeypatch.setattr(reconcile_mod, "session_scope", _boom)
    await reconcile_once()  # must swallow the error and keep state

    assert get_warm_registry().get(flow_id) is not None  # not evicted


async def test_host_get_flow_success_returns_deepcopied_graph(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
):
    """WarmWorkflowHost.get_flow serves a per-request deepcopy of the warm template."""
    from langflow.api.v2.warm_workflow_host import WarmWorkflowHost

    await _clear_flows()
    flow_id = await _insert_flow("served", basic_data, active_user.id)
    await warm_all()

    host = WarmWorkflowHost()
    resolved = await host.get_flow(flow_id, caller=None)

    assert resolved.flow_id == flow_id
    assert len(resolved.graph.vertices) > 0
    # The served graph is a COPY, not the shared template.
    template = get_warm_registry().get(flow_id)[0]
    assert resolved.graph is not template


async def test_reconcile_loop_ticks_then_cancels(monkeypatch):
    """reconcile_loop calls reconcile_once on each interval and stops on cancel."""
    calls = 0

    async def _fake_once():
        nonlocal calls
        calls += 1

    monkeypatch.setattr(reconcile_mod, "reconcile_once", _fake_once)
    task = asyncio.create_task(reconcile_loop(interval=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls >= 1


async def test_prod_lifespan_warms_and_cancels_loop(monkeypatch, tmp_path):
    """Boot the app with LANGFLOW_PROD=true to cover the main.py prod wiring.

    Startup runs the warm block; shutdown cancels the reconcile loop.
    """
    from asgi_lifespan import LifespanManager
    from langflow.main import create_app
    from langflow.services.deps import get_db_service
    from lfx.services.manager import get_service_manager

    db_path = tmp_path / "prod.db"
    monkeypatch.setenv("LANGFLOW_PROD", "true")
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")
    monkeypatch.setenv("DO_NOT_TRACK", "true")

    def _init():
        # Fresh service stack so settings.prod is re-read from the env above.
        get_service_manager().factories.clear()
        get_service_manager().services.clear()
        app = create_app()
        db = get_db_service()
        db.database_url = f"sqlite:///{db_path}"
        db.reload_engine()
        return app

    app = await asyncio.to_thread(_init)
    try:
        # Entering runs startup (the prod warm block); exiting runs shutdown
        # (which cancels the reconcile task). Both must complete without error.
        async with LifespanManager(app, startup_timeout=None, shutdown_timeout=60):
            pass
    finally:
        # Reset the shared service stack so prod settings don't leak to later tests.
        get_service_manager().factories.clear()
        get_service_manager().services.clear()


async def test_prod_lifespan_survives_warm_failure(monkeypatch, tmp_path):
    """A failure in warm_all during prod startup is logged, not fatal (except branch)."""
    from asgi_lifespan import LifespanManager
    from langflow.main import create_app
    from langflow.services.deps import get_db_service
    from lfx.services.manager import get_service_manager

    async def _boom_warm() -> None:
        msg = "warm exploded"
        raise RuntimeError(msg)

    # The lifespan imports warm_all from this module at runtime, so patching the
    # module attribute here makes the prod block hit its except handler.
    monkeypatch.setattr(reconcile_mod, "warm_all", _boom_warm)

    db_path = tmp_path / "prod_fail.db"
    monkeypatch.setenv("LANGFLOW_PROD", "true")
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")
    monkeypatch.setenv("DO_NOT_TRACK", "true")

    def _init():
        get_service_manager().factories.clear()
        get_service_manager().services.clear()
        app = create_app()
        db = get_db_service()
        db.database_url = f"sqlite:///{db_path}"
        db.reload_engine()
        return app

    app = await asyncio.to_thread(_init)
    try:
        # Startup must still complete despite warm_all raising.
        async with LifespanManager(app, startup_timeout=None, shutdown_timeout=60):
            pass
    finally:
        get_service_manager().factories.clear()
        get_service_manager().services.clear()


def test_get_warm_registry_is_singleton(clean_registry):  # noqa: ARG001
    """get_warm_registry returns the same process-local instance."""
    first = get_warm_registry()
    assert isinstance(first, WarmGraphRegistry)
    assert get_warm_registry() is first


# Truthy data (passes the ``not flow.data`` guard) that ``from_payload`` rejects.
_UNBUILDABLE = {"nodes": [{"id": "n1"}], "edges": []}


@contextlib.asynccontextmanager
async def _boom():
    msg = "db down"
    raise RuntimeError(msg)
    yield  # pragma: no cover


async def test_warm_one_db_error_returns_none(clean_registry, monkeypatch):  # noqa: ARG001
    """A DB blip inside warm_one is swallowed -> None (host maps to 404, not 500)."""
    monkeypatch.setattr(reconcile_mod, "session_scope", _boom)
    assert await warm_one("any-id") is None


async def test_warm_all_survives_unbuildable_flow(client, active_user, basic_data, clean_registry):  # noqa: ARG001
    """One flow that fails to build must not abort warming the rest."""
    await _clear_flows()
    good_id = await _insert_flow("good", basic_data, active_user.id)
    await _insert_flow("bad", _UNBUILDABLE, active_user.id)

    await warm_all()

    reg = get_warm_registry()
    assert reg.get(good_id) is not None
    assert len(reg) == 1  # the unbuildable flow was skipped, not fatal


async def test_reconcile_skips_dataless_flow(client, active_user, clean_registry):  # noqa: ARG001
    """A flow with empty data appears in the manifest but is skipped at build time."""
    await _clear_flows()
    await _insert_flow("empty", {}, active_user.id)

    await reconcile_once()

    assert len(get_warm_registry()) == 0


async def test_reconcile_rebuild_error_is_caught(client, active_user, clean_registry):  # noqa: ARG001
    """A flow that fails to build during reconcile is logged, not raised."""
    await _clear_flows()
    await _insert_flow("bad", _UNBUILDABLE, active_user.id)

    await reconcile_once()  # must not raise

    assert len(get_warm_registry()) == 0


async def test_reconcile_change_fetch_error_keeps_registry(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
    monkeypatch,
):
    """If the manifest succeeds but the change-fetch fails, keep state and don't crash."""
    await _clear_flows()
    resident_id = await _insert_flow("resident", basic_data, active_user.id)
    await warm_all()

    # Add a new flow so ``to_build`` is non-empty and the second query runs.
    await _insert_flow("new", basic_data, active_user.id)

    real_scope = reconcile_mod.session_scope
    seen = {"n": 0}

    def _flaky_scope():
        seen["n"] += 1
        # 1st call = manifest (real), 2nd call = change-fetch (boom).
        return _boom() if seen["n"] >= 2 else real_scope()

    monkeypatch.setattr(reconcile_mod, "session_scope", _flaky_scope)
    await reconcile_once()  # must swallow the fetch error

    assert get_warm_registry().get(resident_id) is not None  # unchanged


async def test_reconcile_loop_uses_settings_interval(clean_registry, monkeypatch):  # noqa: ARG001
    """reconcile_loop(None) reads the interval from settings."""
    from types import SimpleNamespace

    calls = 0

    async def _fake_once():
        nonlocal calls
        calls += 1

    monkeypatch.setattr(reconcile_mod, "reconcile_once", _fake_once)
    monkeypatch.setattr(
        reconcile_mod,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(warm_reconcile_interval=0.01)),
    )
    task = asyncio.create_task(reconcile_loop())  # interval=None -> from settings
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert calls >= 1


async def test_resolve_caller_authenticates(monkeypatch):
    """resolve_caller gathers the three credential sources and resolves a user."""
    from langflow.api.v2.warm_workflow_host import WarmWorkflowHost
    from langflow.services.auth import utils as auth_utils

    sentinel = object()

    async def _token(_request):
        return "the-token"

    async def _none(_request):
        return None

    async def _resolve(token, query_param, header_param):
        assert token == "the-token"  # noqa: S105
        assert query_param is None
        assert header_param is None
        return sentinel

    monkeypatch.setattr(auth_utils, "oauth2_login", _token)
    monkeypatch.setattr(auth_utils, "api_key_query", _none)
    monkeypatch.setattr(auth_utils, "api_key_header", _none)
    monkeypatch.setattr(auth_utils, "get_current_user_for_workflow", _resolve)

    host = WarmWorkflowHost()
    assert await host.resolve_caller(request=object()) is sentinel


async def test_reconcile_loop_propagates_cancel(monkeypatch):
    """A CancelledError from reconcile_once is re-raised (never swallowed)."""

    async def _cancel():
        raise asyncio.CancelledError

    monkeypatch.setattr(reconcile_mod, "reconcile_once", _cancel)
    task = asyncio.create_task(reconcile_loop(interval=0.001))
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_reconcile_loop_survives_bad_pass(monkeypatch):
    """A reconcile_once that raises must not kill the loop."""
    calls = 0

    async def _boom_once():
        nonlocal calls
        calls += 1
        msg = "bad pass"
        raise RuntimeError(msg)

    monkeypatch.setattr(reconcile_mod, "reconcile_once", _boom_once)
    task = asyncio.create_task(reconcile_loop(interval=0.01))
    await asyncio.sleep(0.05)
    assert not task.done()  # loop absorbed the error and kept going
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert calls >= 1
