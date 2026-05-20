import asyncio
import uuid
from unittest.mock import MagicMock, patch

import pytest
from langflow.services.tracing.service import TracingService, trace_context_var
from lfx.services.settings.base import Settings
from lfx.services.settings.service import SettingsService

from .test_tracing_service import MockTracer


@pytest.fixture
def tracing_service():
    settings_service = MagicMock(spec=SettingsService)
    # Ensure tracing is NOT deactivated
    settings_service.settings = Settings(deactivate_tracing=False)
    service = TracingService(settings_service)
    service.deactivated = False
    return service


@pytest.mark.asyncio
async def test_nested_flow_tracing_hierarchy(tracing_service):
    run_id = uuid.uuid4()
    run_name = "Outer Flow"
    user_id = "user-1"
    session_id = "session-1"

    # Mock all initializers to avoid real tracer creation, except native
    with (
        patch("langflow.services.tracing.service._get_native_tracer", return_value=MockTracer),
        patch.object(tracing_service, "_initialize_langsmith_tracer"),
        patch.object(tracing_service, "_initialize_langwatch_tracer"),
        patch.object(tracing_service, "_initialize_langfuse_tracer"),
        patch.object(tracing_service, "_initialize_arize_phoenix_tracer"),
        patch.object(tracing_service, "_initialize_opik_tracer"),
        patch.object(tracing_service, "_initialize_traceloop_tracer"),
        patch.object(tracing_service, "_initialize_openlayer_tracer"),
    ):
        # Start Outer Flow
        await tracing_service.start_tracers(run_id=run_id, run_name=run_name, user_id=user_id, session_id=session_id)

        trace_context = trace_context_var.get()
        assert trace_context is not None, "Trace context should be set"
        assert trace_context.ref_count == 1

        # Manually ensure native tracer is in place if Mock didn't trigger
        if "native" not in trace_context.tracers:
            tracing_service._initialize_native_tracer(trace_context)

        native_tracer = trace_context.tracers["native"]

        # Outer Component
        outer_component = MagicMock()
        outer_component.get_vertex.return_value = MagicMock(id="outer-vertex-id")
        outer_component.trace_type = "chain"

        async with tracing_service.trace_component(outer_component, "OuterComponent", inputs={"in": "1"}):
            # Start Inner Flow (Nested)
            # This should increment ref_count of the SAME context
            await tracing_service.start_tracers(
                run_id=uuid.uuid4(), run_name="Inner Flow", user_id=user_id, session_id=session_id
            )
            assert trace_context.ref_count == 2

            # Inner Component
            inner_component = MagicMock()
            inner_component.get_vertex.return_value = MagicMock(id="inner-vertex-id")
            inner_component.trace_type = "llm"

            async with tracing_service.trace_component(inner_component, "InnerComponent", inputs={"in": "2"}):
                # Inside inner component, component_context_var should have parent set
                from langflow.services.tracing.service import component_context_var

                curr_ctx = component_context_var.get()
                assert curr_ctx.trace_id == "inner-vertex-id"
                assert curr_ctx.parent is not None
                assert curr_ctx.parent.trace_id == "outer-vertex-id"

            # End Inner Flow
            await tracing_service.end_tracers(outputs={"inner": "done"})
            assert trace_context.ref_count == 1
            assert trace_context.running is True  # Should still be running

        # End Outer Flow
        await tracing_service.end_tracers(outputs={"outer": "done"})
        assert trace_context.ref_count == 0
        # In TracingService.end_tracers, it calls _stop which sets running=False
        assert trace_context.running is False

    # Verify hierarchy recorded in native_tracer
    await asyncio.sleep(0.1)  # Wait for async queue processing

    assert len(native_tracer.add_trace_list) == 2

    outer_trace = next(t for t in native_tracer.add_trace_list if t["trace_id"] == "outer-vertex-id")
    inner_trace = next(t for t in native_tracer.add_trace_list if t["trace_id"] == "inner-vertex-id")

    assert outer_trace["parent_id"] is None
    assert inner_trace["parent_id"] == "outer-vertex-id"
