"""Tests for lfx.preload — warm-up of core component imports + execution paths.

Pre-warming has two halves, neither of which performs observable execution:
  * importing the core component *classes* (warms the build path, incl. model/agent),
  * running one model-free hermetic flow (warms the execution machinery, no network).
"""

from __future__ import annotations

import asyncio
import sys

import pytest


@pytest.fixture(autouse=True)
def _reset_service_manager():
    """Isolate the process-wide ServiceManager singleton between tests in this module.

    Several tests inject spy services into the global manager and trigger teardown (which
    wipes its registries). Resetting the singleton around each test keeps that shared state
    from leaking and making later tests order-dependent.
    """
    import lfx.services.manager as manager_mod

    manager_mod._service_manager = None
    try:
        yield
    finally:
        manager_mod._service_manager = None


def test_default_core_set_includes_agent():
    """The Agent component must be in the default core set."""
    from lfx.preload import DEFAULT_CORE_COMPONENTS

    assert any(attr == "AgentComponent" for _module, attr in DEFAULT_CORE_COMPONENTS)


def test_prewarm_imports_core_component_submodules():
    """Importing the classes pulls their heavy submodules into the interpreter."""
    from lfx.preload import prewarm_core_imports

    result = prewarm_core_imports(warmup_run=False)

    # Class import (not just package import) loads the submodule — this is the build-path warmth.
    assert "lfx.components.models_and_agents.agent" in sys.modules
    assert "lfx.components.models_and_agents.prompt" in sys.modules
    assert result.failed == {}


def test_warmup_run_opens_no_socket(monkeypatch):
    """The default warm-up run must not open any network connection."""
    import socket

    from lfx.preload import prewarm_core_imports

    def _boom(_self, *_args, **_kwargs):
        msg = "prewarm opened a network connection"
        raise AssertionError(msg)

    monkeypatch.setattr(socket.socket, "connect", _boom)

    result = prewarm_core_imports()

    assert result.warmup_ran is True


def test_warmup_run_does_not_start_tracers():
    """The warm-up run must not emit a trace, even when a tracing service is registered.

    lfx and Langflow share one service manager, so in a Langflow process the hermetic graph
    would otherwise resolve the real tracer and ship a junk "prewarm" trace to a configured
    provider. The run disables tracing on its graph, so start_tracers is never called.
    """
    from lfx.preload import prewarm_core_imports
    from lfx.services.base import Service
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    class _TracingSpy(Service):
        name = "tracing_service"

        def __init__(self) -> None:
            super().__init__()
            self.started = False
            self.deactivated = False

        async def start_tracers(self, *_args, **_kwargs) -> None:
            self.started = True

        async def teardown(self) -> None:
            pass

    spy = _TracingSpy()
    get_service_manager().services[ServiceType.TRACING_SERVICE] = spy

    prewarm_core_imports()

    assert spy.started is False


def test_tracing_disabled_blanks_during_and_restores_absent_key():
    """Prior state #1: key absent -> None during the block, absent again after."""
    from lfx.preload import _tracing_disabled
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    services = get_service_manager().services
    services.pop(ServiceType.TRACING_SERVICE, None)  # ensure absent

    with _tracing_disabled():
        assert services[ServiceType.TRACING_SERVICE] is None  # blanked during
    assert ServiceType.TRACING_SERVICE not in services  # absence restored (popped, not left as None)


def test_tracing_disabled_restores_existing_service():
    """Prior state #2: key present with a real service -> restored to that exact object after."""
    from lfx.preload import _tracing_disabled
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    services = get_service_manager().services
    existing = object()  # stand-in service; restore is an identity check
    services[ServiceType.TRACING_SERVICE] = existing

    with _tracing_disabled():
        assert services[ServiceType.TRACING_SERVICE] is None
    assert services[ServiceType.TRACING_SERVICE] is existing


def test_tracing_disabled_restores_present_none():
    """Prior state #3: key present mapping to None -> stays present-None (NOT popped).

    This is the case the object() sentinel exists for: a plain .get() can't tell it from
    'absent', so without the sentinel the restore would wrongly pop the key.
    """
    from lfx.preload import _tracing_disabled
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    services = get_service_manager().services
    services[ServiceType.TRACING_SERVICE] = None

    with _tracing_disabled():
        assert services[ServiceType.TRACING_SERVICE] is None
    assert ServiceType.TRACING_SERVICE in services  # key kept, not popped
    assert services[ServiceType.TRACING_SERVICE] is None


def test_warmup_run_can_be_skipped():
    """warmup_run=False imports only, with no execution at all."""
    from lfx.preload import prewarm_core_imports

    result = prewarm_core_imports(warmup_run=False)

    assert result.warmup_ran is False


def test_no_freeze_by_default():
    """Freezing is opt-in."""
    from lfx.preload import prewarm_core_imports

    result = prewarm_core_imports(warmup_run=False)

    assert result.froze is False


def test_freeze_runs_gc_freeze():
    """freeze=True moves the warmed heap into GC's permanent generation."""
    import gc

    from lfx.preload import prewarm_core_imports

    gc.unfreeze()
    before = gc.get_freeze_count()
    try:
        result = prewarm_core_imports(warmup_run=False, freeze=True)

        assert result.froze is True
        assert gc.get_freeze_count() > before
    finally:
        gc.unfreeze()


def test_optional_component_failure_is_reported_not_fatal():
    """A non-required component that can't import is recorded, not raised."""
    from lfx.preload import prewarm_core_imports

    result = prewarm_core_imports(
        [("lfx.components.input_output", "ChatInput"), ("lfx.does_not_exist_xyz", "Nope")],
        required=[],
        warmup_run=False,
    )

    assert "lfx.components.input_output:ChatInput" in result.imported
    assert "lfx.does_not_exist_xyz:Nope" in result.failed


def test_required_component_failure_raises():
    """A required component that can't import fails loudly."""
    from lfx.preload import PrewarmError, prewarm_core_imports

    missing = ("lfx.does_not_exist_xyz", "Nope")
    with pytest.raises(PrewarmError):
        prewarm_core_imports([missing], required=[missing], warmup_run=False)


def test_idempotent_second_call():
    """Calling twice succeeds with no failures and does NOT re-import (AC#5)."""
    from lfx.preload import prewarm_core_imports

    prewarm_core_imports(warmup_run=False)
    module_name = "lfx.components.models_and_agents.agent"
    first_module = sys.modules[module_name]

    second = prewarm_core_imports(warmup_run=False)

    assert second.failed == {}
    # importlib.import_module returns the cached module, so the object identity must be
    # unchanged — a second prewarm reuses the warmed module rather than reloading it.
    assert sys.modules[module_name] is first_module


# Cold-start a flow in a fresh interpreter: imports + build + run are all inside the timed
# region. Cold pays the first-time lazy imports (the dominant cost); after prewarm (run
# before t0, mimicking a warm snapshot) those imports are already cached.
_COLD_START = """
import time, asyncio
{prewarm}
t0 = time.perf_counter()
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents import PromptComponent
from lfx.graph.graph.base import Graph
from lfx.schema.schema import InputValueRequest
ci = ChatInput(_id="a"); pr = PromptComponent(_id="b")
pr.set(template="{{m}}", m=ci.message_response)
co = ChatOutput(_id="c"); co.set(input_value=pr.build_prompt)
g = Graph(ci, co); g.prepare()
async def r():
    async for _ in g.async_start(inputs=InputValueRequest(input_value="hi")):
        pass
asyncio.run(r())
print(time.perf_counter() - t0)
"""


def _time_subprocess(script: str) -> float:
    import subprocess
    import sys

    proc = subprocess.run(  # noqa: S603 - fixed interpreter + in-repo script, not untrusted input
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(proc.stdout.strip().splitlines()[-1])


def test_warmup_makes_cold_start_much_faster():
    """A prewarmed interpreter cold-starts a flow dramatically faster than a fresh one.

    Measures the real value: import + build + run in a fresh process. The dominant cold cost
    is first-time imports, which prewarm eliminates — a large, machine-independent margin
    (unlike build+run alone, where the warm benefit is only a few x and CI-noisy).
    """
    cold = _time_subprocess(_COLD_START.format(prewarm=""))
    warmed = _time_subprocess(
        _COLD_START.format(prewarm="from lfx.preload import prewarm_core_imports\nprewarm_core_imports()")
    )

    # Import elimination is worth tens of x everywhere; a 10x floor stays well clear of CI noise.
    assert warmed * 10 < cold, f"warmed={warmed:.4f}s cold={cold:.4f}s"


def _hermetic_flow_payload():
    """A model-free ChatInput -> Prompt -> ChatOutput flow as a loadable payload."""
    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.components.models_and_agents import PromptComponent
    from lfx.graph.graph.base import Graph

    chat_input = ChatInput(_id="ci")
    prompt = PromptComponent(_id="pr")
    prompt.set(template="{m}", m=chat_input.message_response)
    chat_output = ChatOutput(_id="co")
    chat_output.set(input_value=prompt.build_prompt)
    return Graph(chat_input, chat_output).dump(name="hermetic")


def test_run_flow_once_feeds_input_value_through_graph():
    """Regression: input_value must actually reach the flow, not be silently dropped.

    astep reads inputs only via .model_dump(), so a raw dict is ignored and the flow runs
    with empty input. _run_flow_once must wrap input_value in an InputValueRequest so the
    value flows to the output (matters on the --unsafe-run path that runs the real flow).
    """
    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.components.models_and_agents import PromptComponent
    from lfx.graph.graph.base import Graph
    from lfx.preload import _run_flow_once

    sentinel = "prewarm_sentinel_value_xyz"
    chat_input = ChatInput(_id="prewarm_chat_input")
    prompt = PromptComponent(_id="prewarm_prompt")
    prompt.set(template="{warmup}", warmup=chat_input.message_response)
    chat_output = ChatOutput(_id="prewarm_chat_output")
    chat_output.set(input_value=prompt.build_prompt)
    graph = Graph(chat_input, chat_output)
    graph.prepare()

    _run_flow_once(graph, sentinel)

    # With the raw-dict bug the input was dropped and the sentinel never appeared.
    assert sentinel in str(graph.get_vertex("prewarm_chat_output").result)


def test_prewarm_flow_build_only():
    """run=False builds + prepares the specific flow without executing it."""
    from lfx.preload import prewarm_flow

    result = prewarm_flow(_hermetic_flow_payload(), run=False)

    assert result.built is True
    assert result.ran is False
    assert result.error is None


def test_prewarm_flow_run_executes_model_free_flow_with_no_network(monkeypatch):
    """run=True fully executes the flow; a model-free flow opens no socket."""
    import socket

    from lfx.preload import prewarm_flow

    def _boom(_self, *_args, **_kwargs):
        msg = "prewarm_flow opened a network connection"
        raise AssertionError(msg)

    monkeypatch.setattr(socket.socket, "connect", _boom)

    result = prewarm_flow(_hermetic_flow_payload(), run=True)

    assert result.built is True
    assert result.ran is True
    assert result.error is None


def test_prewarm_flow_run_reports_fork_safety():
    """After a run, the result carries a fork-safety check; a model-free run is clean."""
    from lfx.preload import prewarm_flow

    result = prewarm_flow(_hermetic_flow_payload(), run=True)

    assert result.ran is True
    assert isinstance(result.ghost_threads, list)
    # A model-free flow opens no network connections.
    assert result.ghost_connections == []


def test_prewarm_flow_run_surfaces_a_dirty_fork_safety_report(monkeypatch):
    """A run that leaves fork-hostile state must be reported, not hidden.

    Complements the clean-case test: if the process is left with ghost threads/connections,
    prewarm_flow must surface them so a caller can refuse to fork/snapshot a dirty process.
    """
    from lfx.preload import prewarm_flow

    from lfx import fork as fork_mod

    dirty = fork_mod.ForkSafetyReport(
        ghost_threads=["leaked-worker"],
        ghost_connections=["1.2.3.4:5->6.7.8.9:10 (ESTABLISHED)"],
    )
    monkeypatch.setattr(fork_mod, "fork_safety_report", lambda: dirty)

    result = prewarm_flow(_hermetic_flow_payload(), run=True)

    assert result.ran is True
    assert result.ghost_threads == ["leaked-worker"]
    assert result.ghost_connections == ["1.2.3.4:5->6.7.8.9:10 (ESTABLISHED)"]


def test_prewarm_flow_build_only_skips_fork_safety_check():
    """build-only opens nothing, so the fork-safety fields stay empty."""
    from lfx.preload import prewarm_flow

    result = prewarm_flow(_hermetic_flow_payload(), run=False)

    assert result.ghost_threads == []
    assert result.ghost_connections == []


def test_prewarm_flow_captures_error_without_raising():
    """A flow that can't be loaded reports an error instead of raising."""
    from lfx.preload import prewarm_flow

    result = prewarm_flow("/nonexistent/flow_xyz.json", run=False)

    assert result.built is False
    assert result.error is not None


def test_prewarm_flow_freeze():
    """freeze=True freezes the heap after warming the flow."""
    import gc

    from lfx.preload import prewarm_flow

    gc.unfreeze()
    before = gc.get_freeze_count()
    try:
        result = prewarm_flow(_hermetic_flow_payload(), run=False, freeze=True)

        assert result.froze is True
        assert gc.get_freeze_count() > before
    finally:
        gc.unfreeze()


# ---------------------------------------------------------------------------
# Service teardown before fork/snapshot (fork-safety for pluggable services)
# ---------------------------------------------------------------------------


from lfx.services.base import Service  # noqa: E402


class _PreloadSpyService(Service):
    """Minimal Service that records teardown and can be flipped to raise.

    Stands in for a real pluggable service (DB/cache/telemetry) whose teardown
    must run before a fork. Injected directly into the global service manager.
    """

    def __init__(self, name: str, *, fail: bool = False) -> None:
        super().__init__()
        self._name = name
        self._fail = fail
        self.torn_down = False

    @property
    def name(self) -> str:
        return self._name

    async def teardown(self) -> None:
        self.torn_down = True
        if self._fail:
            msg = f"{self._name} teardown boom"
            raise RuntimeError(msg)


def _inject_spy(name: str = "tracing_spy", *, fail: bool = False) -> _PreloadSpyService:
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    spy = _PreloadSpyService(name, fail=fail)
    # Occupy a real slot so a warmup run's lazy get() won't recreate over it.
    get_service_manager().services[ServiceType.TRACING_SERVICE] = spy
    return spy


def _drop_spy() -> None:
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    get_service_manager().services.pop(ServiceType.TRACING_SERVICE, None)


def test_core_imports_tears_down_services_by_default():
    """The fork-safe base path disposes services instantiated during warming."""
    from lfx.preload import prewarm_core_imports

    spy = _inject_spy()
    try:
        result = prewarm_core_imports(warmup_run=False)
        assert result.services_torn_down is True
        assert spy.torn_down is True
    finally:
        _drop_spy()


def test_core_imports_keeps_services_when_opted_out():
    """teardown_services=False keeps warmed live instances (Firecracker snapshot)."""
    from lfx.preload import prewarm_core_imports

    spy = _inject_spy()
    try:
        result = prewarm_core_imports(warmup_run=False, teardown_services=False)
        assert result.services_torn_down is False
        assert spy.torn_down is False
    finally:
        _drop_spy()


def test_teardown_warm_services_raises_on_failure():
    """A fork-safety-critical teardown failure is fatal (PrewarmError)."""
    from lfx.preload import PrewarmError, teardown_warm_services

    _inject_spy("bad_service", fail=True)
    try:
        with pytest.raises(PrewarmError, match="teardown before fork/snapshot failed"):
            teardown_warm_services()
    finally:
        _drop_spy()


class _LoopBoundSpyService(Service):
    """Service holding an asyncio resource bound to a different event loop.

    Stands in for a plugin (asyncpg pool / aiohttp session) that bound a resource to the
    warm-up loop; teardown runs in a new loop and awaiting it there raises the cross-loop
    error. (A pending Future, not a Lock — an uncontended Lock takes a fast path that never
    binds to a loop on 3.12+.)
    """

    def __init__(self, name: str = "loopbound_spy") -> None:
        super().__init__()
        self._name = name
        self.torn_down = False
        # A pending future owned by a separate loop (loop A).
        self._loop = asyncio.new_event_loop()
        self._fut = self._loop.create_future()

    @property
    def name(self) -> str:
        return self._name

    async def teardown(self) -> None:
        self.torn_down = True
        # Awaiting loop A's future from teardown's loop (loop B) -> cross-loop RuntimeError.
        await self._fut

    def close(self) -> None:
        if not self._fut.done():
            self._fut.cancel()
        self._loop.close()


def test_teardown_cross_loop_resource_failure_is_fatal_not_silent():
    """A service resource bound to a prior loop fails teardown loudly (PrewarmError).

    Exercises the documented hazard: warming runs flows in throwaway asyncio.run loops, so
    teardown happens in a new loop; a loop-bound plugin resource must fail-safe (refuse the
    fork) rather than be captured dirty.
    """
    from lfx.preload import PrewarmError, teardown_warm_services
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    spy = _LoopBoundSpyService()
    get_service_manager().services[ServiceType.TRACING_SERVICE] = spy
    try:
        with pytest.raises(PrewarmError, match="teardown before fork/snapshot failed"):
            teardown_warm_services()
        assert spy.torn_down is True  # teardown was attempted before it failed
    finally:
        _drop_spy()
        spy.close()

    # Confirm the underlying cause really is the cross-loop binding (not some other error),
    # using a fresh resource so we're not re-awaiting an already-consumed future.
    cause_spy = _LoopBoundSpyService()
    try:
        with pytest.raises(RuntimeError, match="attached to a different loop"):
            asyncio.run(cause_spy.teardown())
    finally:
        cause_spy.close()


def test_flow_build_only_tears_down_services():
    """prewarm_flow(run=False) is fork-safe and disposes services."""
    from lfx.preload import prewarm_flow

    spy = _inject_spy()
    try:
        result = prewarm_flow(_hermetic_flow_payload(), run=False)
        assert result.services_torn_down is True
        assert spy.torn_down is True
    finally:
        _drop_spy()


def test_flow_run_does_not_tear_down_services():
    """prewarm_flow(run=True) intentionally leaves live connections (Firecracker)."""
    from lfx.preload import prewarm_flow

    spy = _inject_spy()
    try:
        result = prewarm_flow(_hermetic_flow_payload(), run=True)
        assert result.services_torn_down is False
        assert spy.torn_down is False
    finally:
        _drop_spy()


def test_flow_teardown_failure_is_captured_in_error_not_raised():
    """A teardown failure during build-only warming goes into .error, never raised.

    prewarm_flow's contract is that one bad flow can't abort a multi-flow loop, so a
    teardown PrewarmError must be funneled into result.error like build/run failures.
    """
    from lfx.preload import prewarm_flow

    _inject_spy("bad_service", fail=True)
    try:
        result = prewarm_flow(_hermetic_flow_payload(), run=False)  # must NOT raise
        assert result.error is not None
        assert "teardown" in result.error.lower()
        assert result.services_torn_down is False
    finally:
        _drop_spy()


def test_flow_build_failure_still_tears_down_services():
    """A failed build must not skip teardown — partial state would leave the process fork-unsafe."""
    from lfx.preload import prewarm_flow

    spy = _inject_spy()
    try:
        result = prewarm_flow("/nonexistent/flow_xyz.json", run=False)  # build fails
        assert result.built is False
        assert result.error is not None
        # Teardown is still attempted despite the build error, so the process stays fork-safe.
        assert spy.torn_down is True
        assert result.services_torn_down is True
    finally:
        _drop_spy()


def test_flow_build_and_teardown_failures_are_both_reported():
    """When both the build and teardown fail, .error preserves both, not just the last."""
    from lfx.preload import prewarm_flow

    _inject_spy("bad_service", fail=True)
    try:
        result = prewarm_flow("/nonexistent/flow_xyz.json", run=False)
        assert "FileNotFoundError" in result.error or "No such file" in result.error
        assert "teardown failed" in result.error
    finally:
        _drop_spy()
