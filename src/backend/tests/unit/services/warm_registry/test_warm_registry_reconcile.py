"""DB-backed tests for the warm registry: reconcile, real graph build, host success.

Unlike ``test_warm_registry.py`` (hermetic, ``_build`` stubbed), these use the
``client`` fixture to boot a real service stack + test DB, insert real ``Flow``
rows, and drive the ACTUAL ``warm_all`` / ``warm_one`` / ``reconcile_once`` /
``reconcile_loop`` against the ``flow`` table — building real ``Graph`` templates
and resolving them through the shared warm run seam (``warm_graph``).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
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


@pytest.fixture(autouse=True)
def enable_bounded_preload_for_reconcile_tests(monkeypatch):
    """This module exercises eager warming explicitly; production defaults lazy."""
    original = reconcile_mod.get_settings_service

    def _get_settings_service():
        service = original()
        settings = service.settings.model_copy(update={"warm_registry_preload_limit": 100})
        return SimpleNamespace(settings=settings)

    monkeypatch.setattr(reconcile_mod, "get_settings_service", _get_settings_service)


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


async def _empty_flow_data(flow_id: str) -> None:
    """Blank a flow's executable data and bump updated_at (a real 'emptied' edit)."""
    await _replace_flow_data(flow_id, {})


async def _replace_flow_data(flow_id: str, data: dict) -> None:
    """Replace a flow's executable data and bump its change marker."""
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))).first()
        flow.data = data
        flow.updated_at = datetime.now(timezone.utc)
        session.add(flow)


async def _delete_flow(flow_id: str) -> None:
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))).first()
        await session.delete(flow)


async def _clear_flow_version(flow_id: str) -> None:
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))).first()
        flow.updated_at = None
        session.add(flow)


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


async def test_unversioned_flow_stays_cold_and_evicts_a_previous_entry(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
):
    """A nullable legacy timestamp cannot safely identify executable revisions."""
    await _clear_flows()
    flow_id = await _insert_flow("unversioned", basic_data, active_user.id)
    await warm_all()
    assert get_warm_registry().get(flow_id) is not None

    await _clear_flow_version(flow_id)
    await reconcile_once()

    assert get_warm_registry().get(flow_id) is None
    assert await warm_one(flow_id) is None


async def test_warm_one_by_uuid_and_endpoint_name(client, active_user, basic_data, clean_registry):  # noqa: ARG001
    await _clear_flows()
    flow_id = await _insert_flow("by-name", basic_data, active_user.id, endpoint_name="my-endpoint")

    # Lookup by UUID caches under the canonical id.
    hit = await warm_one(flow_id)
    assert hit is not None
    assert get_warm_registry().get(flow_id) is not None

    # A fresh registry: lookup by endpoint name resolves and caches under the UUID.
    service_mod._warm_registry = None
    hit_by_name = await warm_one("my-endpoint", user_id=active_user.id)
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


async def test_enabled_lifespan_warms_and_cancels_loop(monkeypatch, tmp_path):
    """Boot with the warm registry enabled to cover the main.py lifespan wiring.

    Startup runs the warm block; shutdown cancels the reconcile loop.
    """
    from asgi_lifespan import LifespanManager
    from langflow.main import create_app
    from langflow.services.deps import get_db_service
    from lfx.services.manager import get_service_manager

    db_path = tmp_path / "warm_enabled.db"
    monkeypatch.setenv("LANGFLOW_WARM_REGISTRY_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")
    monkeypatch.setenv("DO_NOT_TRACK", "true")

    def _init():
        # Fresh service stack booted from the env above.
        get_service_manager().factories.clear()
        get_service_manager().services.clear()
        app = create_app()
        db = get_db_service()
        db.database_url = f"sqlite:///{db_path}"
        db.reload_engine()
        return app

    app = await asyncio.to_thread(_init)
    try:
        # Entering runs startup (the warm block); exiting runs shutdown
        # (which cancels the reconcile task). Both must complete without error.
        async with LifespanManager(app, startup_timeout=None, shutdown_timeout=60):
            pass
    finally:
        # Reset the shared service stack so warm settings don't leak to later tests.
        get_service_manager().factories.clear()
        get_service_manager().services.clear()


async def test_enabled_lifespan_survives_warm_failure(monkeypatch, tmp_path):
    """A failure in warm_all during enabled startup is logged, not fatal."""
    from asgi_lifespan import LifespanManager
    from langflow.main import create_app
    from langflow.services.deps import get_db_service
    from lfx.services.manager import get_service_manager

    async def _boom_warm() -> None:
        msg = "warm exploded"
        raise RuntimeError(msg)

    # The lifespan imports warm_all from this module at runtime, so patching the
    # module attribute here makes the warm block hit its except handler.
    monkeypatch.setattr(reconcile_mod, "warm_all", _boom_warm)

    db_path = tmp_path / "warm_fail.db"
    monkeypatch.setenv("LANGFLOW_WARM_REGISTRY_ENABLED", "true")
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


async def test_warm_one_db_error_raises_unavailable(clean_registry, monkeypatch):  # noqa: ARG001
    """A DB availability failure inside warm_one raises FlowStoreUnavailableError (-> 503)."""
    from langflow.services.warm_registry.service import FlowStoreUnavailableError

    monkeypatch.setattr(reconcile_mod, "session_scope", _boom)
    with pytest.raises(FlowStoreUnavailableError):
        await warm_one("any-id")


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


async def test_reconcile_evicts_flow_whose_data_becomes_empty(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
):
    """A resident flow edited to empty data must be evicted, not left stale."""
    await _clear_flows()
    flow_id = await _insert_flow("full", basic_data, active_user.id)
    await warm_all()
    assert get_warm_registry().get(flow_id) is not None

    # Emptying the flow's data (with a version bump) makes it non-runnable.
    await _empty_flow_data(flow_id)
    await reconcile_once()

    # The stale template is gone (pre-fix this stayed resident forever).
    assert get_warm_registry().get(flow_id) is None


async def test_reconcile_failed_changed_build_evicts_stale_graph(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
    monkeypatch,
):
    """A truthy changed flow that fails to rebuild must not retain its old graph."""
    await _clear_flows()
    flow_id = await _insert_flow("bad", basic_data, active_user.id)
    await warm_all()
    assert get_warm_registry().get(flow_id) is not None

    await _replace_flow_data(flow_id, _UNBUILDABLE)

    await reconcile_once()  # must not raise

    assert get_warm_registry().get(flow_id) is None

    # The matching failed revision is excluded from the full-row fetch on later
    # passes. Only the narrow manifest session should be opened.
    real_scope = reconcile_mod.session_scope
    scope_calls = 0

    def _counting_scope():
        nonlocal scope_calls
        scope_calls += 1
        return real_scope()

    monkeypatch.setattr(reconcile_mod, "session_scope", _counting_scope)
    await reconcile_once()
    assert scope_calls == 1


async def test_reconcile_tombstone_does_not_starve_older_preload_candidate(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
    monkeypatch,
):
    """A rejected newest row must not consume the only preload slot forever."""
    await _clear_flows()
    good_id = await _insert_flow("older-good", basic_data, active_user.id)
    bad_id = await _insert_flow("newer-bad", _UNBUILDABLE, active_user.id)
    await _touch_flow(bad_id, "newer-bad")

    settings = reconcile_mod.get_settings_service().settings.model_copy(update={"warm_registry_preload_limit": 1})
    monkeypatch.setattr(
        reconcile_mod,
        "get_settings_service",
        lambda: SimpleNamespace(settings=settings),
    )

    await reconcile_once()
    registry = get_warm_registry()
    assert registry.get(bad_id) is None
    assert registry.rejection_count() == 1

    await reconcile_once()

    assert registry.get(good_id) is not None
    assert registry.get(bad_id) is None


async def test_reconcile_empty_newest_flow_does_not_starve_older_preload_candidate(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
    monkeypatch,
):
    """A versioned empty row is rejected so the next pass can fill its slot."""
    await _clear_flows()
    good_id = await _insert_flow("older-good", basic_data, active_user.id)
    empty_id = await _insert_flow("newer-empty", {}, active_user.id)
    await _touch_flow(empty_id, "newer-empty")

    settings = reconcile_mod.get_settings_service().settings.model_copy(update={"warm_registry_preload_limit": 1})
    monkeypatch.setattr(
        reconcile_mod,
        "get_settings_service",
        lambda: SimpleNamespace(settings=settings),
    )

    await reconcile_once()
    registry = get_warm_registry()
    assert registry.get(empty_id) is None
    assert registry.rejection_count() == 1

    await reconcile_once()

    assert registry.get(good_id) is not None
    assert registry.get(empty_id) is None


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


# ── #2: deferred host selection (fixes import-time-vs-env-file ordering) ──────


def _api_req(**kw):
    from langflow.api.v1.schemas import SimplifiedAPIRequest

    return SimplifiedAPIRequest(**kw)


def _flow_obj(flow_id_str: str, data: dict):
    from langflow.services.database.models.flow.model import Flow

    return Flow(id=UUID(flow_id_str), name="warm", data=data)


def testflow_needs_auto_globals_detects_eligible_empty_field():
    from langflow.api.warm_graph import flow_needs_auto_globals

    def _tmpl(field):
        return {"nodes": [{"data": {"node": {"template": {"k": field}}}}]}

    assert flow_needs_auto_globals(_tmpl({"type": "str", "show": True, "value": "", "display_name": "Key"})) is True
    # filled value -> not eligible
    assert flow_needs_auto_globals(_tmpl({"type": "str", "show": True, "value": "x", "display_name": "Key"})) is False
    # explicit load_from_db -> not eligible (already bound)
    explicit_field = {"type": "str", "value": "", "load_from_db": True, "display_name": "Key"}
    explicit = {"nodes": [{"data": {"node": {"template": {"k": explicit_field}}}}]}
    assert flow_needs_auto_globals(explicit) is False
    assert flow_needs_auto_globals(None) is False


async def test_try_warm_returns_none_when_disabled(client, active_user, basic_data, clean_registry):  # noqa: ARG001
    """The default-off warm seam is inert, so the cold path runs."""
    from langflow.api import warm_graph

    flow = _flow_obj(str(UUID(int=1)), basic_data)
    assert await warm_graph.try_warm_run_graph(flow, _api_req(), user_id=active_user.id, context=None) is None


async def test_try_warm_hit_returns_deepcopy_with_identity(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
    monkeypatch,
):
    """Enabled + no tweaks + non-auto-bind + warm hit returns a run-local graph."""
    from langflow.api import warm_graph

    await _clear_flows()
    flow_id = await _insert_flow("warm", basic_data, active_user.id)
    await warm_all()

    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _s: True)
    # Isolate the registry-hit behavior from auto-bind detection (tested separately);
    # Basic Prompting happens to have an eligible empty field, which is its own test.
    monkeypatch.setattr(warm_graph, "flow_needs_auto_globals", lambda _d: False)

    # Use the same persisted revision that was authorized/resolved by the request
    # path. A synthetic Flow gets a fresh default ``updated_at`` and must correctly
    # miss the revision-bound registry entry.
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == UUID(flow_id)))).first()
    assert flow is not None
    graph = await warm_graph.try_warm_run_graph(flow, _api_req(), user_id=active_user.id, context=None)

    assert graph is not None
    assert len(graph.vertices) > 0
    assert str(graph.user_id) == str(active_user.id)
    # It's a copy, not the shared template.
    assert graph is not get_warm_registry().get(flow_id)[0]


async def test_try_warm_cold_on_tweaks(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
    monkeypatch,
):
    from langflow.api import warm_graph

    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _s: True)
    monkeypatch.setattr(warm_graph, "flow_needs_auto_globals", lambda _d: False)
    flow = _flow_obj(str(UUID(int=2)), basic_data)
    req = _api_req(tweaks={"n": {"f": "v"}})
    assert await warm_graph.try_warm_run_graph(flow, req, user_id=active_user.id, context=None) is None


async def test_try_warm_cold_on_context(
    client,  # noqa: ARG001
    active_user,
    basic_data,
    clean_registry,  # noqa: ARG001
    monkeypatch,
):
    from langflow.api import warm_graph

    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _s: True)
    monkeypatch.setattr(warm_graph, "flow_needs_auto_globals", lambda _d: False)
    flow = _flow_obj(str(UUID(int=3)), basic_data)
    assert await warm_graph.try_warm_run_graph(flow, _api_req(), user_id=active_user.id, context={"x": 1}) is None


async def test_try_warm_cold_on_auto_bind_flow(
    client,  # noqa: ARG001
    active_user,
    clean_registry,  # noqa: ARG001
    monkeypatch,
):
    """A flow with an eligible empty str field must NOT be warm-served (auto-bind gap)."""
    from langflow.api import warm_graph

    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _s: True)
    auto_bind_field = {"type": "str", "show": True, "value": "", "display_name": "Key"}
    auto_bind_data = {"nodes": [{"data": {"node": {"template": {"k": auto_bind_field}}}}]}
    flow = _flow_obj(str(UUID(int=4)), auto_bind_data)
    assert await warm_graph.try_warm_run_graph(flow, _api_req(), user_id=active_user.id, context=None) is None
