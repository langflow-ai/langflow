"""Tests for lfx.preload — warm-up of core component imports + execution paths.

Pre-warming has two halves, neither of which performs observable execution:
  * importing the core component *classes* (warms the build path, incl. model/agent),
  * running one model-free hermetic flow (warms the execution machinery, no network).
"""

from __future__ import annotations

import sys

import pytest


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
    """Calling twice succeeds with no failures."""
    from lfx.preload import prewarm_core_imports

    prewarm_core_imports(warmup_run=False)
    second = prewarm_core_imports(warmup_run=False)

    assert second.failed == {}


# Build + run a hermetic flow, timing only that region. Cold pays the lazy import/run cost.
_BUILD_RUN = """
import time, asyncio
{prewarm}
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents import PromptComponent
from lfx.graph.graph.base import Graph
{start}
ci = ChatInput(_id="a"); pr = PromptComponent(_id="b")
pr.set(template="{{m}}", m=ci.message_response)
co = ChatOutput(_id="c"); co.set(input_value=pr.build_prompt)
g = Graph(ci, co); g.prepare()
async def r():
    async for _ in g.async_start(inputs={{"input_value": "hi"}}):
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


def test_warmup_makes_subsequent_build_run_much_faster():
    """After a full prewarm, a fresh build+run is dramatically faster than cold."""
    cold = _time_subprocess(_BUILD_RUN.format(prewarm="", start="t0 = time.perf_counter()"))
    warmed = _time_subprocess(
        _BUILD_RUN.format(
            prewarm="from lfx.preload import prewarm_core_imports\nprewarm_core_imports()",
            start="t0 = time.perf_counter()",
        )
    )

    # Observed locally ~55x; assert a conservative floor to stay non-flaky.
    assert warmed * 5 < cold, f"warmed={warmed:.4f}s cold={cold:.4f}s"


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
