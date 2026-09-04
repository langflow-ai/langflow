"""Verify flow_executor.py routes through the executor coordinator."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import pytest
from lfx.execution import (
    Coordinator,
    ExecutorRegistry,
    reset_default_coordinator,
    set_default_coordinator,
)
from lfx.execution.executor import Executor
from lfx.execution.types import RunComplete, StepResult


class _Recording(Executor):
    kind = "in-process"

    def __init__(self) -> None:
        self.units_seen: list[Any] = []

    async def execute(self, unit):
        self.units_seen.append(unit)
        yield StepResult(payload=object())
        yield RunComplete(outputs=[])


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_default_coordinator()
    yield
    reset_default_coordinator()


@pytest.mark.asyncio
async def test_run_graph_uses_default_coordinator():
    from dataclasses import dataclass, field

    from langflow.agentic.services.flow_executor import _run_graph_with_events
    from langflow.agentic.services.flow_types import FlowExecutionResult

    recording = _Recording()
    registry = ExecutorRegistry()
    registry.register(recording)
    set_default_coordinator(Coordinator(registry=registry))

    @dataclass
    class _FakeGraph:
        flow_id: str | None = None
        flow_name: str | None = None
        user_id: str | None = None
        session_id: str | None = None
        context: dict = field(default_factory=dict)

        def prepare(self):
            pass

        @contextlib.contextmanager
        def flow_execution_span(self, *, make_current: bool = True):
            """The caller opens the flow span now, so a stand-in graph has to offer one.

            Without it the AttributeError is swallowed by the broad except in
            _run_graph_with_events and the coordinator is never reached, which reads as "the
            coordinator was not used" rather than "the fake is missing a method".
            """
            _ = make_current
            yield

    queue: asyncio.Queue = asyncio.Queue()
    execution_result = FlowExecutionResult()

    from lfx.events.event_manager import create_default_event_manager

    em = create_default_event_manager(asyncio.Queue())
    await _run_graph_with_events(
        graph=_FakeGraph(),
        input_value="hi",
        global_variables=None,
        user_id=None,
        session_id=None,
        event_manager=em,
        event_queue=queue,
        execution_result=execution_result,
    )

    assert len(recording.units_seen) == 1
