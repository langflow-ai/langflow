"""Tests for capability-driven coordinator routing."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from lfx.execution.coordinator import Coordinator
from lfx.execution.executor import Executor
from lfx.execution.registry import ExecutorRegistry
from lfx.execution.types import RunComplete, StepResult, Unit
from lfx.services.capability import CapabilityClaims, CapabilityContext, CapabilityService, Trust

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence


class _StubSettings:
    settings = type("Settings", (), {})()


class _RecordingExecutor(Executor):
    def __init__(self, kind: str, output: str) -> None:
        self.kind = kind
        self.output = output
        self.units: list[Unit] = []

    async def execute(self, unit: Unit) -> AsyncIterator[StepResult | RunComplete]:
        self.units.append(unit)
        yield RunComplete(outputs=[self.output])


class _NeverEndingExecutor(Executor):
    kind = "sandbox"

    def __init__(self) -> None:
        self.closed = False

    async def execute(self, unit: Unit) -> AsyncIterator[StepResult | RunComplete]:  # noqa: ARG002
        try:
            while True:
                yield StepResult(payload="tick")
                await asyncio.sleep(0)
        finally:
            self.closed = True


@pytest.mark.asyncio
async def test_coordinator_routes_untrusted_runs_to_capability_executor() -> None:
    sandbox = _RecordingExecutor("sandbox", "sandbox-output")
    registry = ExecutorRegistry()
    registry.register(_RecordingExecutor("in-process", "in-process-output"))
    registry.register(sandbox)

    class _Classifier:
        def trust_of_flow(self, context: CapabilityContext) -> Trust:
            assert context.user_id == "graph-user"
            assert context.flow_id == "graph-flow"
            return Trust.UNTRUSTED

        def is_untrusted_node(self, _node: dict[str, Any], _context: CapabilityContext | None = None) -> bool:
            return True

    class _Resolver:
        def resolve(self, context: CapabilityContext) -> str:
            assert context.run_id == "runtime-run"
            return f"tenant:{context.user_id}"

    class _Provider:
        def mint(
            self,
            *,
            context: CapabilityContext,
            tenant_id: str,
            component_id: str | None,
            scopes: Sequence[str],
            ttl_seconds: int = 600,  # noqa: ARG002
        ) -> str:
            assert context.runtime_options["run_id"] == "runtime-run"
            assert tenant_id == "tenant:graph-user"
            assert component_id is None
            assert tuple(scopes) == ("variables:read",)
            return f"token:{context.user_id}:{context.flow_id}"

        def verify(self, token: str) -> CapabilityClaims:  # noqa: ARG002
            return CapabilityClaims(tenant_id="tenant:graph-user", user_id="graph-user")

    capability_service = CapabilityService(settings_service=_StubSettings())
    capability_service.install(
        provider=_Provider(),
        classifier=_Classifier(),
        resolver=_Resolver(),
        untrusted_executor_kind="sandbox",
    )
    coordinator = Coordinator(
        registry=registry,
        executor_kind="in-process",
        capability_service=capability_service,
    )

    graph = SimpleNamespace(user_id="graph-user", flow_id="graph-flow")
    outputs = await coordinator.run_to_completion(
        graph,
        inputs=[{}],
        run_id="runtime-run",
        capability_scopes=["variables:read"],
    )

    assert outputs == ["sandbox-output"]
    assert len(sandbox.units) == 1
    assert sandbox.units[0].executor_kind == "sandbox"
    expected_token = "token:graph-user:graph-flow"  # noqa: S105
    assert sandbox.units[0].runtime_options["lfx_capability_token"] == expected_token
    assert sandbox.units[0].runtime_options["lfx_tenant_id"] == "tenant:graph-user"
    assert sandbox.units[0].runtime_options["lfx_trust"] == "untrusted"


@pytest.mark.asyncio
async def test_coordinator_skips_capability_service_when_passthrough() -> None:
    default = _RecordingExecutor("in-process", "default-output")
    registry = ExecutorRegistry()
    registry.register(default)
    capability_service = CapabilityService(settings_service=_StubSettings())
    coordinator = Coordinator(
        registry=registry,
        executor_kind="in-process",
        capability_service=capability_service,
    )

    outputs = await coordinator.run_to_completion(SimpleNamespace(), inputs=[{}])

    assert outputs == ["default-output"]
    assert default.units[0].executor_kind is None
    assert default.units[0].runtime_options == {}


@pytest.mark.asyncio
async def test_stream_close_finalizes_capability_selected_executor() -> None:
    sandbox = _NeverEndingExecutor()
    registry = ExecutorRegistry()
    registry.register(_RecordingExecutor("in-process", "in-process-output"))
    registry.register(sandbox)

    class _Classifier:
        def trust_of_flow(self, _context: CapabilityContext) -> Trust:
            return Trust.UNTRUSTED

        def is_untrusted_node(self, _node: dict[str, Any], _context: CapabilityContext | None = None) -> bool:
            return True

    capability_service = CapabilityService(settings_service=_StubSettings())
    capability_service.install(classifier=_Classifier(), untrusted_executor_kind="sandbox")
    coordinator = Coordinator(
        registry=registry,
        executor_kind="in-process",
        capability_service=capability_service,
    )

    stream = coordinator.stream(SimpleNamespace(), inputs=[{}])
    assert await anext(stream) == "tick"
    await stream.aclose()
    await asyncio.sleep(0)

    assert sandbox.closed is True
