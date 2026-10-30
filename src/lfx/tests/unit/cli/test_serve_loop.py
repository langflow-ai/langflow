"""Unit tests for event loop selection in ``lfx serve``."""

import asyncio
import importlib.util
import os
import subprocess
import sys

import pytest
import uvicorn
from lfx.cli.serve_loop import (
    AUTO_LOOP,
    EVENT_LOOP_ENV,
    ZUVLOOP,
    ZUVLOOP_LOOP_FACTORY,
    resolve_loop,
)

ZUVLOOP_INSTALLED = importlib.util.find_spec("zuvloop") is not None

# Resolves the loop in a brand-new interpreter and prints the module its loop object
# comes from. A fresh interpreter inherits none of this process's state, so what it
# prints is both the spawn-safety check and the answer to "which loop actually ran".
_LOOP_PROBE = (
    "import uvicorn;"
    "from lfx.cli.serve_loop import resolve_loop;"
    "config = uvicorn.Config('lfx.cli.serve_loop:resolve_loop', loop=resolve_loop());"
    "loop = config.get_loop_factory()();"
    "print('LOOP_MODULE', type(loop).__module__);"
    "loop.close()"
)

# Same idea for the gunicorn worker: its loop is chosen when the class is imported, so
# the only way to see the env reflected in it is to import it in a fresh interpreter.
_WORKER_PROBE = (
    "from lfx.cli.serve_gunicorn import LFXUvicornWorker;"
    "from lfx.cli.serve_loop import resolve_loop;"
    "print('WORKER_LOOP', LFXUvicornWorker.CONFIG_KWARGS['loop']);"
    "print('RESOLVED', resolve_loop())"
)


def _run_probe(code, **env):
    """Run a probe in a fresh interpreter and return its tagged output lines."""
    result = subprocess.run(  # noqa: S603 - this interpreter and an in-test script, not untrusted input
        [sys.executable, "-c", code],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, f"probe exited {result.returncode}: {result.stderr}"
    tagged = {}
    for line in result.stdout.splitlines():
        tag, _, value = line.partition(" ")
        if tag.isupper():
            tagged[tag] = value.strip()
    return tagged


async def _unused_app(_scope, _receive, _send):
    """Spawn tests disable lifespan and open no listening sockets."""
    msg = "The spawned server should not call the app"
    raise AssertionError(msg)


class TestResolveLoop:
    """``resolve_loop`` always returns a loop choice uvicorn can resolve."""

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

    @pytest.mark.skipif(not ZUVLOOP_INSTALLED, reason="needs zuvloop (Python 3.14+)")
    @pytest.mark.parametrize("value", ["zuvloop", "ZUVLOOP", "  zuvloop  "])
    def test_zuvloop_selection_is_case_and_space_insensitive(self, monkeypatch, value):
        monkeypatch.setenv(EVENT_LOOP_ENV, value)
        assert resolve_loop() == ZUVLOOP_LOOP_FACTORY

    @pytest.mark.skipif(not ZUVLOOP_INSTALLED, reason="needs zuvloop (Python 3.14+)")
    def test_renamed_factory_attribute_falls_back(self, monkeypatch):
        """A zuvloop without the entry point degrades the loop, it does not kill the boot."""
        import zuvloop

        monkeypatch.setenv(EVENT_LOOP_ENV, ZUVLOOP)
        monkeypatch.delattr(zuvloop, "new_event_loop")
        assert resolve_loop() == AUTO_LOOP


class TestZuvloopFactoryString:
    """The string handed to uvicorn, checked on every interpreter including CI's."""

    def test_factory_string_is_the_documented_entry_point(self):
        """Pins the value itself: a typo here exits the server at boot, not in a test."""
        assert ZUVLOOP_LOOP_FACTORY == "zuvloop:new_event_loop"

    def test_uvicorn_can_parse_the_factory_string(self):
        """Uvicorn's own importer accepts the shape, whether or not zuvloop is here."""
        from uvicorn.importer import ImportFromStringError, import_from_string

        if ZUVLOOP_INSTALLED:
            import zuvloop

            assert import_from_string(ZUVLOOP_LOOP_FACTORY) is zuvloop.new_event_loop
        else:
            with pytest.raises(ImportFromStringError) as excinfo:
                import_from_string(ZUVLOOP_LOOP_FACTORY)
            # The complaint must be the missing module, not a malformed string: a value
            # uvicorn cannot even parse (say a bare "zuvloop") exits the process.
            assert 'Could not import module "zuvloop"' in str(excinfo.value)


class TestServedLoop:
    """Which loop a fresh interpreter actually ends up serving on."""

    def test_default_does_not_serve_on_zuvloop(self):
        tagged = _run_probe(_LOOP_PROBE, **{EVENT_LOOP_ENV: ""})
        assert not tagged["LOOP_MODULE"].startswith("zuvloop")

    @pytest.mark.skipif(not ZUVLOOP_INSTALLED, reason="needs zuvloop (Python 3.14+)")
    def test_zuvloop_env_serves_on_zuvloop(self):
        tagged = _run_probe(_LOOP_PROBE, **{EVENT_LOOP_ENV: ZUVLOOP})
        assert tagged["LOOP_MODULE"].startswith("zuvloop")

    @pytest.mark.skipif(ZUVLOOP_INSTALLED, reason="covers the interpreters without zuvloop")
    def test_zuvloop_env_falls_back_when_unavailable(self):
        tagged = _run_probe(_LOOP_PROBE, **{EVENT_LOOP_ENV: ZUVLOOP})
        assert not tagged["LOOP_MODULE"].startswith("zuvloop")


class TestGunicornWorkerLoop:
    """``lfx serve --workers N`` carries the selection into its uvicorn config."""

    def test_worker_config_kwargs_are_accepted_by_uvicorn(self):
        from lfx.cli.serve_gunicorn import LFXUvicornWorker

        config = uvicorn.Config(_unused_app, **LFXUvicornWorker.CONFIG_KWARGS)
        assert config.loop == LFXUvicornWorker.CONFIG_KWARGS["loop"]
        assert config.get_loop_factory() is not None

    def test_worker_loop_matches_the_resolved_loop(self):
        """Catches the worker dropping the override: both come from the same process."""
        tagged = _run_probe(_WORKER_PROBE, **{EVENT_LOOP_ENV: ZUVLOOP})
        assert tagged["WORKER_LOOP"] == tagged["RESOLVED"]


@pytest.mark.skipif(not ZUVLOOP_INSTALLED, reason="needs zuvloop (Python 3.14+)")
class TestZuvloopFactory:
    """Uvicorn can create the selected loop in this process and in spawned workers."""

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

    def test_spawned_worker_boots_and_exits_cleanly(self, monkeypatch):
        """A real uvicorn worker survives the selection through spawn.

        Exiting 0 is all this asserts, and `auto` exits 0 too, so it is a smoke test
        for the spawn path. ``TestServedLoop`` is what pins the loop identity.
        """
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
