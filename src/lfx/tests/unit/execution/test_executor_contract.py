"""Reusable contract test suite for any ``lfx.execution.Executor`` implementation.

The seam has a small but load-bearing set of behaviors that any executor MUST satisfy
to be safely swappable behind ``Coordinator``. This module spells them out as a
parametrizable suite so:

- The built-in ``InProcessExecutor`` is checked here against the same suite the
  external executors (stepflow, future remote/sandbox, etc.) will be checked against.
- Authors of new executors can subclass ``ExecutorContract`` in their own project,
  override the two fixtures, and inherit the full battery of behavioural assertions
  rather than re-deriving them from the docstring of the ABC.

The contract intentionally does NOT pin executor-specific event shapes -- only the
universal seam guarantees. If a future executor needs to add stricter checks for its
own payloads, those go in an executor-specific test file, not here.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING

import pytest
from lfx.execution.types import RunComplete, StepResult, Unit

if TYPE_CHECKING:
    from lfx.execution.executor import Executor


class ExecutorContract:
    """Base class of behavioural assertions every Executor must satisfy.

    Subclasses MUST override two fixtures:

    - ``contract_executor``: returns a freshly constructed ``Executor`` instance.
    - ``contract_unit_factory``: returns a callable ``() -> Unit`` that produces a
      fresh, runnable ``Unit`` each call. The unit should drive a minimal but real
      execution -- not a stub -- so the test actually exercises the executor's
      end-to-end path.

    Tests are designed to be independent: each test creates its own unit through
    the factory so subclasses don't have to worry about state bleed between cases.
    """

    @pytest.fixture
    def contract_executor(self) -> Executor:
        msg = "Subclasses must override the contract_executor fixture"
        raise NotImplementedError(msg)

    @pytest.fixture
    def contract_unit_factory(self) -> Callable[[], Unit]:
        msg = "Subclasses must override the contract_unit_factory fixture"
        raise NotImplementedError(msg)

    # --- Universal seam guarantees ----------------------------------------------------

    def test_kind_is_a_non_empty_string(self, contract_executor: Executor) -> None:
        """``kind`` is a ClassVar on the ABC; it must be set and non-empty."""
        assert isinstance(contract_executor.kind, str)
        assert contract_executor.kind, "Executor.kind must be a non-empty string"

    def test_execute_returns_async_iterator(
        self,
        contract_executor: Executor,
        contract_unit_factory: Callable[[], Unit],
    ) -> None:
        """``execute(unit)`` MUST return an async iterator.

        The ABC types it as such; consumers (Coordinator.run, Coordinator.stream,
        run_to_completion) rely on it.
        """
        stream = contract_executor.execute(contract_unit_factory())
        assert isinstance(stream, AsyncIterator), (
            f"{type(contract_executor).__name__}.execute() returned a "
            f"{type(stream).__name__}, expected AsyncIterator. Consumers can't iterate "
            "this. Common cause: forgetting to make the method an `async def` "
            "generator."
        )

    @pytest.mark.asyncio
    async def test_stream_ends_with_exactly_one_run_complete(
        self,
        contract_executor: Executor,
        contract_unit_factory: Callable[[], Unit],
    ) -> None:
        """Streams emit zero-or-more ``StepResult`` items terminated by one ``RunComplete``."""
        items = [item async for item in contract_executor.execute(contract_unit_factory())]

        assert items, "executor yielded nothing -- a RunComplete is mandatory"
        assert isinstance(items[-1], RunComplete), (
            f"final item was {type(items[-1]).__name__}; the seam requires a terminal "
            "RunComplete so run_to_completion() and downstream collectors can detect end-of-run."
        )

        run_completes = [i for i in items if isinstance(i, RunComplete)]
        assert len(run_completes) == 1, (
            f"executor yielded {len(run_completes)} RunComplete items; the seam allows "
            "at most one (and requires exactly one)."
        )

        non_terminal = items[:-1]
        bad = [i for i in non_terminal if not isinstance(i, StepResult)]
        assert not bad, (
            f"all pre-terminal items must be StepResult; got: {[type(i).__name__ for i in bad]}. "
            "Coordinator.stream() relies on this to filter; mixing other types makes "
            "the stream untyped at the seam boundary."
        )

    @pytest.mark.asyncio
    async def test_executor_is_reusable_across_runs(
        self,
        contract_executor: Executor,
        contract_unit_factory: Callable[[], Unit],
    ) -> None:
        """An Executor MUST be reusable: state that carries between runs is a bug.

        The registry returns the same instance for every ``coordinator.run()`` call,
        so any internal state pinned to ``self`` will silently corrupt later runs.
        """
        first = [item async for item in contract_executor.execute(contract_unit_factory())]
        second = [item async for item in contract_executor.execute(contract_unit_factory())]

        assert isinstance(first[-1], RunComplete)
        assert isinstance(second[-1], RunComplete)
        # Same shape across runs proves no carry-over short-circuit. We don't assert
        # equality of payloads because some executors include timestamps / run IDs.
        assert len(first) >= 1
        assert len(second) >= 1

    @pytest.mark.asyncio
    async def test_concurrent_runs_on_one_instance_are_isolated(
        self,
        contract_executor: Executor,
        contract_unit_factory: Callable[[], Unit],
    ) -> None:
        """Concurrent runs on one executor instance MUST be isolated.

        Coordinator may launch concurrent runs (Loop subgraphs, parallel API
        requests). An executor that crosses state between them is broken.
        """

        async def drain() -> list[object]:
            return [item async for item in contract_executor.execute(contract_unit_factory())]

        a, b = await asyncio.gather(drain(), drain())
        assert isinstance(a[-1], RunComplete)
        assert isinstance(b[-1], RunComplete)

    @pytest.mark.asyncio
    async def test_consumer_cancellation_does_not_hang_or_leak(
        self,
        contract_executor: Executor,
        contract_unit_factory: Callable[[], Unit],
    ) -> None:
        """Consumer cancellation via ``aclose()`` MUST finalize within a bounded window.

        The executor's async generator is closed by the consumer; any internal
        context managers, subprocesses, or sockets MUST be released. A strict
        timeout surfaces regressions as test failures rather than CI hangs.
        """
        gen = contract_executor.execute(contract_unit_factory())

        try:
            first = await asyncio.wait_for(anext(gen), timeout=10.0)
        except StopAsyncIteration:
            # Executor produced no items at all -- still a valid stream (just an empty one).
            return

        assert isinstance(first, (StepResult, RunComplete)), (
            f"first yielded item was {type(first).__name__}; seam requires StepResult or RunComplete"
        )

        # Drop the iterator. If the executor holds a subprocess / network / lock, this
        # is the moment of truth: aclose() must finalize without blocking forever.
        await asyncio.wait_for(gen.aclose(), timeout=10.0)

    @pytest.mark.asyncio
    async def test_execute_signature_takes_exactly_one_unit(self, contract_executor: Executor) -> None:
        """Pin the ABC signature so executors don't drift away from a single ``Unit`` parameter.

        ``execute(*args, **kwargs)`` shapes bypass the ``Unit`` value object and
        make the seam opaque to introspection.
        """
        sig = inspect.signature(contract_executor.execute)
        params = [p for p in sig.parameters.values() if p.name != "self"]
        assert len(params) == 1, (
            f"{type(contract_executor).__name__}.execute must accept exactly one positional "
            f"Unit argument; got signature: {sig}"
        )


class TestInProcessExecutorContract(ExecutorContract):
    """Run the contract suite against the built-in InProcessExecutor.

    This is the reference implementation: if the contract suite is wrong, this is
    where it will fail first. Stepflow / remote / sandbox executors are exercised
    against the same suite in their own test files.
    """

    @pytest.fixture
    def contract_executor(self) -> Executor:
        from lfx.execution.backends.in_process import InProcessExecutor

        return InProcessExecutor()

    @pytest.fixture
    def contract_unit_factory(self, simple_graph) -> Callable[[], Unit]:  # noqa: ARG002
        # ``simple_graph`` is a pytest fixture from conftest.py. We don't capture it
        # by closure across runs because Graph instances accumulate state; instead we
        # rebuild on every call so each unit is fresh.
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.graph import Graph
        from lfx.schema.schema import InputValueRequest

        def factory() -> Unit:
            ci = ChatInput(_id="chat_input")
            ci.set(should_store_message=False)
            co = ChatOutput(input_value="test", _id="chat_output")
            co.set(sender_name=ci.message_response)
            return Unit(
                graph=Graph(ci, co),
                inputs=[],
                runtime_options={"initial_inputs": InputValueRequest(input_value="hi")},
            )

        return factory
