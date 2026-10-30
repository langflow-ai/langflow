"""Unit tests for event loop selection in ``lfx serve``."""

import asyncio
import importlib.util
import sys

import pytest
import uvicorn
from lfx.cli.serve_loop import AUTO_LOOP, EVENT_LOOP_ENV, ZUVLOOP, resolve_loop

ZUVLOOP_INSTALLED = importlib.util.find_spec("zuvloop") is not None
HAS_LOOP_FACTORIES = hasattr(uvicorn.config, "LOOP_FACTORIES")


async def _unused_app(_scope, _receive, _send):
    """Spawn tests disable lifespan and open no listening sockets."""
    msg = "The spawned server should not call the app"
    raise AssertionError(msg)


class TestResolveLoop:
    """``resolve_loop`` always returns a loop name uvicorn can resolve."""

    def test_unset_env_serves_on_auto(self, monkeypatch):
        monkeypatch.delenv(EVENT_LOOP_ENV, raising=False)
        assert resolve_loop() == AUTO_LOOP

    def test_empty_env_serves_on_auto(self, monkeypatch):
        monkeypatch.setenv(EVENT_LOOP_ENV, "   ")
        assert resolve_loop() == AUTO_LOOP

    def test_explicit_auto_serves_on_auto(self, monkeypatch):
        monkeypatch.setenv(EVENT_LOOP_ENV, "auto")
        assert resolve_loop() == AUTO_LOOP

    def test_unknown_loop_falls_back_to_auto(self, monkeypatch):
        monkeypatch.setenv(EVENT_LOOP_ENV, "tokio")
        assert resolve_loop() == AUTO_LOOP

    def test_zuvloop_falls_back_when_not_installed(self, monkeypatch):
        monkeypatch.setenv(EVENT_LOOP_ENV, ZUVLOOP)
        monkeypatch.setitem(sys.modules, "zuvloop", None)
        assert resolve_loop() == AUTO_LOOP

    def test_zuvloop_falls_back_without_loop_factories(self, monkeypatch):
        monkeypatch.setenv(EVENT_LOOP_ENV, ZUVLOOP)
        monkeypatch.delattr(uvicorn.config, "LOOP_FACTORIES", raising=False)
        assert resolve_loop() == AUTO_LOOP

    @pytest.mark.skipif(not ZUVLOOP_INSTALLED, reason="needs zuvloop (Python 3.14+)")
    @pytest.mark.parametrize("value", ["zuvloop", "ZUVLOOP", "  zuvloop  "])
    def test_zuvloop_selection_is_case_and_space_insensitive(self, monkeypatch, value):
        monkeypatch.setenv(EVENT_LOOP_ENV, value)
        expected = "zuvloop:new_event_loop" if HAS_LOOP_FACTORIES else AUTO_LOOP
        assert resolve_loop() == expected


@pytest.mark.skipif(not ZUVLOOP_INSTALLED, reason="needs zuvloop (Python 3.14+)")
@pytest.mark.skipif(not HAS_LOOP_FACTORIES, reason="needs uvicorn>=0.36")
class TestZuvloopFactory:
    """Uvicorn can create the selected loop in this process and spawned workers."""

    def test_factory_builds_a_usable_event_loop(self, monkeypatch):
        import zuvloop

        monkeypatch.setenv(EVENT_LOOP_ENV, ZUVLOOP)
        config = uvicorn.Config(_unused_app, loop=resolve_loop())
        factory = config.get_loop_factory()
        assert factory is zuvloop.new_event_loop
        loop = factory()
        try:
            assert isinstance(loop, asyncio.AbstractEventLoop)
            assert loop.run_until_complete(asyncio.sleep(0, result="ok")) == "ok"
        finally:
            loop.close()

    def test_spawned_worker_can_resolve_selected_loop(self, monkeypatch):
        from uvicorn._subprocess import get_subprocess

        monkeypatch.setenv(EVENT_LOOP_ENV, ZUVLOOP)
        config = uvicorn.Config(_unused_app, loop=resolve_loop(), workers=2, lifespan="off", log_level="error")
        server = uvicorn.Server(config)
        server.should_exit = True
        process = get_subprocess(config=config, target=server.run, sockets=[])
        process.start()
        try:
            process.join(timeout=15)
            assert not process.is_alive(), "Spawned worker did not exit"
            assert process.exitcode == 0
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join(timeout=5)
            process.close()
