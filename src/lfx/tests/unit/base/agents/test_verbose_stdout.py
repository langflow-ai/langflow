"""Regression tests for the agent ``verbose`` stdout chain markers.

Issue: ``> Entering new None chain... / > Finished chain.`` were printed to stdout
on every Agent execution regardless of ``LANGCHAIN_VERBOSE=false`` because the base
agent's ``verbose`` input defaulted to ``True`` and was passed straight to
``AgentExecutor``, which attaches a ``StdOutCallbackHandler`` that prints via
``print()`` -- bypassing Langflow's logging system.

See https://github.com/langflow-ai/langflow/issues/13662.
"""

import io
from contextlib import redirect_stdout

import pytest
from langchain_classic.agents import AgentExecutor
from langchain_core.agents import AgentFinish
from langchain_core.runnables import RunnableLambda
from lfx.base.agents.utils import resolve_agent_verbose

CHAIN_MARKERS = ("Entering new", "Finished chain")


class TestResolveAgentVerbose:
    """``resolve_agent_verbose`` is the single source of truth for the flag."""

    def test_defaults_to_false_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LANGCHAIN_VERBOSE", raising=False)
        assert resolve_agent_verbose() is False

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "on", " on "])
    def test_truthy_env_enables(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        monkeypatch.setenv("LANGCHAIN_VERBOSE", value)
        assert resolve_agent_verbose() is True

    @pytest.mark.parametrize("value", ["false", "False", "0", "no", "off", "", "anything"])
    def test_falsy_or_other_env_disables(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        monkeypatch.setenv("LANGCHAIN_VERBOSE", value)
        assert resolve_agent_verbose() is False


def _build_executor(*, verbose: bool) -> AgentExecutor:
    """Build a minimal real ``AgentExecutor`` the way the legacy agent path does."""

    def _finish(_inputs: dict) -> AgentFinish:
        return AgentFinish(return_values={"output": "done"}, log="done")

    return AgentExecutor.from_agent_and_tools(
        agent=RunnableLambda(_finish),
        tools=[],
        handle_parsing_errors=True,
        verbose=verbose,
        max_iterations=5,
    )


class TestAgentExecutorStdout:
    """End-to-end: the markers must not reach stdout unless explicitly opted in."""

    def test_no_chain_markers_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LANGCHAIN_VERBOSE", raising=False)
        executor = _build_executor(verbose=resolve_agent_verbose())

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            executor.invoke({"input": "hello"})

        captured = buffer.getvalue()
        assert not any(marker in captured for marker in CHAIN_MARKERS), captured

    def test_falsy_env_suppresses_chain_markers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Matches the issue's exact reproduction: LANGCHAIN_VERBOSE=false.
        monkeypatch.setenv("LANGCHAIN_VERBOSE", "false")
        executor = _build_executor(verbose=resolve_agent_verbose())

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            executor.invoke({"input": "hello"})

        captured = buffer.getvalue()
        assert not any(marker in captured for marker in CHAIN_MARKERS), captured

    def test_truthy_env_emits_chain_markers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Guards against a false-negative: prove the markers DO print when opted in,
        # so the suppression assertions above are meaningful.
        monkeypatch.setenv("LANGCHAIN_VERBOSE", "true")
        executor = _build_executor(verbose=resolve_agent_verbose())

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            executor.invoke({"input": "hello"})

        captured = buffer.getvalue()
        assert any(marker in captured for marker in CHAIN_MARKERS), captured
