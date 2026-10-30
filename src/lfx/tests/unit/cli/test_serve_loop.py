"""Unit tests for event loop selection in ``lfx serve``."""

import asyncio
import importlib.util

import pytest
from lfx.cli.serve_loop import AUTO_LOOP, EVENT_LOOP_ENV, ZUVLOOP, resolve_loop, zuvloop_loop_factory

ZUVLOOP_INSTALLED = importlib.util.find_spec("zuvloop") is not None


@pytest.fixture(autouse=True)
def _restore_loop_registry():
    """Keep uvicorn's process-wide loop registry unchanged across tests."""
    from uvicorn.config import LOOP_FACTORIES

    before = dict(LOOP_FACTORIES)
    yield
    LOOP_FACTORIES.clear()
    LOOP_FACTORIES.update(before)


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

    def test_unknown_loop_leaves_registry_untouched(self, monkeypatch):
        from uvicorn.config import LOOP_FACTORIES

        monkeypatch.setenv(EVENT_LOOP_ENV, "tokio")
        resolve_loop()
        assert "tokio" not in LOOP_FACTORIES

    @pytest.mark.skipif(ZUVLOOP_INSTALLED, reason="zuvloop is installed; this covers the absent case")
    def test_zuvloop_falls_back_when_not_installed(self, monkeypatch):
        monkeypatch.setenv(EVENT_LOOP_ENV, ZUVLOOP)
        assert resolve_loop() == AUTO_LOOP

    @pytest.mark.skipif(not ZUVLOOP_INSTALLED, reason="needs zuvloop (Python 3.14+)")
    def test_zuvloop_selected_when_installed(self, monkeypatch):
        monkeypatch.setenv(EVENT_LOOP_ENV, ZUVLOOP)
        assert resolve_loop() == ZUVLOOP

    @pytest.mark.skipif(not ZUVLOOP_INSTALLED, reason="needs zuvloop (Python 3.14+)")
    def test_zuvloop_registered_in_uvicorn_registry(self, monkeypatch):
        from uvicorn.config import LOOP_FACTORIES

        monkeypatch.setenv(EVENT_LOOP_ENV, ZUVLOOP)
        resolve_loop()
        assert LOOP_FACTORIES[ZUVLOOP] == "lfx.cli.serve_loop:zuvloop_loop_factory"

    @pytest.mark.skipif(not ZUVLOOP_INSTALLED, reason="needs zuvloop (Python 3.14+)")
    @pytest.mark.parametrize("value", ["ZUVLOOP", "  zuvloop  "])
    def test_env_value_is_case_and_space_insensitive(self, monkeypatch, value):
        monkeypatch.setenv(EVENT_LOOP_ENV, value)
        assert resolve_loop() == ZUVLOOP


class TestZuvloopFactory:
    """The registered import string and the factory it names."""

    def test_registered_path_is_importable_by_uvicorn(self):
        """Guards the registry string against a typo, with or without zuvloop installed."""
        from uvicorn.importer import import_from_string

        assert import_from_string("lfx.cli.serve_loop:zuvloop_loop_factory") is zuvloop_loop_factory

    @pytest.mark.skipif(not ZUVLOOP_INSTALLED, reason="needs zuvloop (Python 3.14+)")
    def test_factory_builds_a_usable_event_loop(self):
        loop = zuvloop_loop_factory()()
        try:
            assert isinstance(loop, asyncio.AbstractEventLoop)
            assert loop.run_until_complete(asyncio.sleep(0, result="ok")) == "ok"
        finally:
            loop.close()
