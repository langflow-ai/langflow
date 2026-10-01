"""The lifespan freezes the startup heap out of the cyclic GC once per worker.

Each test boots a real app with ``freeze_heap`` replaced by a recorder, so the
pytest process's own heap is never frozen.
"""

from __future__ import annotations

import asyncio

from langflow import main as main_mod
from langflow.services.warm_registry import reconcile as reconcile_mod


async def _boot(monkeypatch, tmp_path, events: list[str], *, warm: bool, freeze: bool) -> None:
    from asgi_lifespan import LifespanManager
    from langflow.services.deps import get_db_service
    from lfx.services.manager import get_service_manager

    monkeypatch.setattr(main_mod, "freeze_heap", lambda: events.append("freeze"))
    db_path = tmp_path / "gc_freeze.db"
    monkeypatch.setenv("LANGFLOW_GC_FREEZE_AFTER_STARTUP", str(freeze).lower())
    monkeypatch.setenv("LANGFLOW_WARM_REGISTRY_ENABLED", str(warm).lower())
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")
    monkeypatch.setenv("DO_NOT_TRACK", "true")

    def _init():
        get_service_manager().factories.clear()
        get_service_manager().services.clear()
        app = main_mod.create_app()
        db = get_db_service()
        db.database_url = f"sqlite:///{db_path}"
        db.reload_engine()
        return app

    app = await asyncio.to_thread(_init)
    try:
        async with LifespanManager(app, startup_timeout=None, shutdown_timeout=60):
            events.append("started")
            if warm:
                # The warm registry task freezes off the startup path.
                for _ in range(200):
                    if "reconcile" in events:
                        break
                    await asyncio.sleep(0.05)
    finally:
        get_service_manager().factories.clear()
        get_service_manager().services.clear()


async def test_freezes_once_at_startup_without_warm_registry(monkeypatch, tmp_path):
    events: list[str] = []

    await _boot(monkeypatch, tmp_path, events, warm=False, freeze=True)

    assert events == ["freeze", "started"]


async def test_freezes_once_after_warm_preload(monkeypatch, tmp_path):
    events: list[str] = []

    async def _warm_all() -> None:
        events.append("warm")

    async def _reconcile_loop() -> None:
        events.append("reconcile")
        await asyncio.Event().wait()

    # The lifespan imports these from the module at runtime.
    monkeypatch.setattr(reconcile_mod, "warm_all", _warm_all)
    monkeypatch.setattr(reconcile_mod, "reconcile_loop", _reconcile_loop)

    await _boot(monkeypatch, tmp_path, events, warm=True, freeze=True)

    assert events.count("freeze") == 1
    assert events.index("warm") < events.index("freeze") < events.index("reconcile")


async def test_setting_off_skips_freeze(monkeypatch, tmp_path):
    events: list[str] = []

    await _boot(monkeypatch, tmp_path, events, warm=False, freeze=False)

    assert events == ["started"]
