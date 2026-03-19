import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.services.tracing.base import BaseTracer
from langflow.services.tracing.otlp import _reset_shared_provider
from langflow.services.tracing.service import (
    TracingService,
    component_context_var,
    trace_context_var,
)
from lfx.services.settings.base import Settings
from lfx.services.settings.service import SettingsService


@pytest.fixture(autouse=True)
def _reset_otlp_provider():
    """Reset the shared OTLP TracerProvider before and after each test.

    Ensures test isolation since the singleton persists across test runs.
    """
    _reset_shared_provider()
    yield
    _reset_shared_provider()


class MockTracer(BaseTracer):
    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: uuid.UUID,
        flow_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        tracing_user_id: str | None = None,
    ) -> None:
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.flow_id = flow_id
        self.user_id = user_id
        self.session_id = session_id
        self.tracing_user_id = tracing_user_id
        self._ready = True
        self.end_called = False
        self.get_langchain_callback_called = False
        self.add_trace_list = []
        self.end_trace_list = []

    @property
    def ready(self) -> bool:
        return self._ready

    def add_trace(
        self,
        trace_id: str,
        trace_name: str,
        trace_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        vertex=None,
    ) -> None:
        self.add_trace_list.append(
            {
                "trace_id": trace_id,
                "trace_name": trace_name,
                "trace_type": trace_type,
                "inputs": inputs,
                "metadata": metadata,
                "vertex": vertex,
            }
        )

    def end_trace(
        self,
        trace_id: str,
        trace_name: str,
        outputs: dict[str, Any] | None = None,
        error: Exception | None = None,
        logs=(),
    ) -> None:
        self.end_trace_list.append(
            {
                "trace_id": trace_id,
                "trace_name": trace_name,
                "outputs": outputs,
                "error": error,
                "logs": logs,
            }
        )

    def end(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: Exception | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.end_called = True
        self.inputs_param = inputs
        self.outputs_param = outputs
        self.error_param = error
        self.metadata_param = metadata

    def get_langchain_callback(self):
        self.get_langchain_callback_called = True
        return MagicMock()


@pytest.fixture
def mock_settings_service():
    settings = Settings()
    settings.deactivate_tracing = False
    return SettingsService(settings, MagicMock())


@pytest.fixture
def tracing_service(mock_settings_service):
    return TracingService(mock_settings_service)


@pytest.fixture
def mock_component():
    component = MagicMock()
    mock_vertex = MagicMock()
    mock_vertex.id = "test_vertex_id"
    component._vertex = mock_vertex
    component.get_vertex = MagicMock(return_value=mock_vertex)
    component.trace_type = "test_trace_type"
    return component


@pytest.fixture
def mock_tracers():
    with (
        patch(
            "langflow.services.tracing.service._get_langsmith_tracer",
            return_value=MockTracer,
        ),
        patch(
            "langflow.services.tracing.service._get_langwatch_tracer",
            return_value=MockTracer,
        ),
        patch(
            "langflow.services.tracing.service._get_langfuse_tracer",
            return_value=MockTracer,
        ),
        patch(
            "langflow.services.tracing.service._get_arize_phoenix_tracer",
            return_value=MockTracer,
        ),
        patch(
            "langflow.services.tracing.service._get_opik_tracer",
            return_value=MockTracer,
        ),
        patch(
            "langflow.services.tracing.service._get_traceloop_tracer",
            return_value=MockTracer,
        ),
        patch(
            "langflow.services.tracing.service._get_native_tracer",
            return_value=MockTracer,
        ),
        patch(
            "langflow.services.tracing.service._get_openlayer_tracer",
            return_value=MockTracer,
        ),
        patch(
            "langflow.services.tracing.service._get_otlp_tracer",
            return_value=MockTracer,
        ),
    ):
        yield


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_tracers")
async def test_start_end_tracers(tracing_service):
    """Test starting and ending tracers."""
    run_id = uuid.uuid4()
    run_name = "test_run"
    user_id = "test_user"
    session_id = "test_session"
    project_name = "test_project"
    outputs = {"output_key": "output_value"}

    await tracing_service.start_tracers(run_id, run_name, user_id, session_id, project_name)
    # Verify trace_context is set correctly
    trace_context = trace_context_var.get()
    assert trace_context is not None
    assert trace_context.run_id == run_id
    assert trace_context.run_name == run_name
    assert trace_context.project_name == project_name
    assert trace_context.user_id == user_id
    assert trace_context.session_id == session_id

    # Verify tracers are initialized
    assert "langsmith" in trace_context.tracers
    assert "langwatch" in trace_context.tracers
    assert "langfuse" in trace_context.tracers
    assert "arize_phoenix" in trace_context.tracers
    assert "opik" in trace_context.tracers
    assert "traceloop" in trace_context.tracers
    assert "native" in trace_context.tracers
    assert "openlayer" in trace_context.tracers
    assert "otlp" in trace_context.tracers

    await tracing_service.end_tracers(outputs)

    # Verify end method was called for all tracers
    trace_context = trace_context_var.get()
    for tracer in trace_context.tracers.values():
        assert tracer.end_called
        assert tracer.metadata_param == outputs
        assert tracer.outputs_param == trace_context.all_outputs

    # Verify worker_task is cancelled
    assert trace_context.worker_task is None
    assert not trace_context.running


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_tracers")
async def test_start_tracers_forwards_tracing_user_id_to_langfuse(tracing_service):
    """``tracing_user_id`` reaches Langfuse as a distinct field; ``user_id`` stays the auth user.

    Regression for GitHub issue #9505: the LangFuseTracer keeps ``user_id`` as
    the authenticated Langflow user (backwards compat) and exposes the override
    on ``tracing_user_id``. The tracer stamps the override into trace metadata
    rather than redefining ``trace.userId``.
    """
    run_id = uuid.uuid4()
    await tracing_service.start_tracers(
        run_id,
        "run",
        "auth-uuid",
        "session-abc",
        "project",
        tracing_user_id="end-user-123",
    )

    trace_context = trace_context_var.get()
    langfuse = trace_context.tracers["langfuse"]
    assert langfuse.user_id == "auth-uuid"
    assert langfuse.tracing_user_id == "end-user-123"
    # The shared trace context mirrors the same separation.
    assert trace_context.user_id == "auth-uuid"
    assert trace_context.tracing_user_id == "end-user-123"


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_tracers")
async def test_start_tracers_without_override_keeps_auth_user_and_no_tracing_user_id(tracing_service):
    """Without an override, ``user_id`` is the auth user and ``tracing_user_id`` is None."""
    run_id = uuid.uuid4()
    await tracing_service.start_tracers(run_id, "run", "auth-uuid", "session-abc", "project")

    langfuse = trace_context_var.get().tracers["langfuse"]
    assert langfuse.user_id == "auth-uuid"
    assert langfuse.tracing_user_id is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_tracers")
async def test_trace_component(tracing_service, mock_component):
    """Test component tracing context manager."""
    run_id = uuid.uuid4()
    run_name = "test_run"
    user_id = "test_user"
    session_id = "test_session"
    project_name = "test_project"

    trace_name = "test_component_trace"
    inputs = {"input_key": "input_value"}
    metadata = {"metadata_key": "metadata_value"}

    await tracing_service.start_tracers(run_id, run_name, user_id, session_id, project_name)

    async with tracing_service.trace_component(mock_component, trace_name, inputs, metadata) as ts:
        # Verify component context is set
        component_context = component_context_var.get()
        assert component_context is not None
        assert component_context.trace_id == mock_component._vertex.id
        assert component_context.trace_name == trace_name
        assert component_context.trace_type == mock_component.trace_type
        assert component_context.vertex == mock_component._vertex
        assert component_context.inputs == inputs
        assert component_context.inputs_metadata == metadata

        # Verify add_trace method was called for tracers
        await asyncio.sleep(0.1)  # Wait for async queue processing
        trace_context = trace_context_var.get()
        for tracer in trace_context.tracers.values():
            assert tracer.add_trace_list[0]["trace_id"] == mock_component._vertex.id
            assert tracer.add_trace_list[0]["trace_name"] == trace_name
            assert tracer.add_trace_list[0]["trace_type"] == mock_component.trace_type
            assert tracer.add_trace_list[0]["inputs"] == inputs
            assert tracer.add_trace_list[0]["metadata"] == metadata
            assert tracer.add_trace_list[0]["vertex"] == mock_component._vertex

        # Test adding logs
        ts.add_log(trace_name, {"message": "test log"})
        assert {"message": "test log"} in component_context.logs[trace_name]

        # Test setting outputs
        outputs = {"output_key": "output_value"}
        output_metadata = {"output_metadata_key": "output_metadata_value"}
        ts.set_outputs(trace_name, outputs, output_metadata)
        assert component_context.outputs[trace_name] == outputs
        assert component_context.outputs_metadata[trace_name] == output_metadata
        assert trace_context.all_outputs[trace_name] == outputs

    # Verify end_trace method was called for tracers
    await asyncio.sleep(0.1)  # Wait for async queue processing
    for tracer in trace_context.tracers.values():
        assert tracer.end_trace_list[0]["trace_id"] == mock_component._vertex.id
        assert tracer.end_trace_list[0]["trace_name"] == trace_name
        assert tracer.end_trace_list[0]["outputs"] == trace_context.all_outputs[trace_name]
        assert tracer.end_trace_list[0]["error"] is None
        assert tracer.end_trace_list[0]["logs"] == component_context.logs[trace_name]

    # Cleanup
    await tracing_service.end_tracers({})


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_tracers")
async def test_trace_component_with_exception(tracing_service, mock_component):
    """Test component tracing context manager with exception handling."""
    run_id = uuid.uuid4()
    run_name = "test_run"
    user_id = "test_user"
    session_id = "test_session"
    project_name = "test_project"

    trace_name = "test_component_trace"
    inputs = {"input_key": "input_value"}

    await tracing_service.start_tracers(run_id, run_name, user_id, session_id, project_name)

    test_exception = ValueError("Test exception")

    with pytest.raises(ValueError, match="Test exception"):
        async with tracing_service.trace_component(mock_component, trace_name, inputs):
            raise test_exception

    # Verify end_trace method was called with exception
    await asyncio.sleep(0.1)  # Wait for async queue processing
    trace_context = trace_context_var.get()
    for tracer in trace_context.tracers.values():
        assert tracer.end_trace_list[0]["error"] == test_exception

    # Cleanup
    await tracing_service.end_tracers({})


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_tracers")
async def test_get_langchain_callbacks(tracing_service):
    """Test getting LangChain callback handlers."""
    run_id = uuid.uuid4()
    run_name = "test_run"
    user_id = "test_user"
    session_id = "test_session"
    project_name = "test_project"

    await tracing_service.start_tracers(run_id, run_name, user_id, session_id, project_name)

    callbacks = tracing_service.get_langchain_callbacks()

    # Verify get_langchain_callback method was called for each tracer
    trace_context = trace_context_var.get()
    for tracer in trace_context.tracers.values():
        assert tracer.get_langchain_callback_called

    # Verify returned callbacks list length
    expected = len(trace_context_var.get().tracers)
    assert len(callbacks) == expected

    # Cleanup
    await tracing_service.end_tracers({})


@pytest.mark.asyncio
async def test_deactivated_tracing(mock_settings_service):
    """Test deactivated tracing functionality."""
    # Set deactivate_tracing to True
    mock_settings_service.settings.deactivate_tracing = True
    tracing_service = TracingService(mock_settings_service)

    run_id = uuid.uuid4()
    run_name = "test_run"
    user_id = "test_user"
    session_id = "test_session"
    project_name = "test_project"

    # Starting tracers should have no effect
    await tracing_service.start_tracers(run_id, run_name, user_id, session_id, project_name)

    # With tracing disabled, trace_context_var may be None or uninitialized
    assert trace_context_var.get() is None
    # We don't need to check trace_context_var state, just verify tracing operations don't execute

    # Test trace_component context manager
    mock_component = MagicMock()
    trace_name = "test_component_trace"
    inputs = {"input_key": "input_value"}

    async with tracing_service.trace_component(mock_component, trace_name, inputs) as ts:
        ts.add_log(trace_name, {"message": "test log"})
        ts.set_outputs(trace_name, {"output_key": "output_value"})

        # Test getting LangChain callback handlers
        callbacks = tracing_service.get_langchain_callbacks()
        assert len(callbacks) == 0  # Should return empty list when tracing is disabled

    # Test end_tracers
    await tracing_service.end_tracers({})


@pytest.mark.asyncio
async def test_cleanup_inputs():
    """Test cleaning sensitive information from input data."""
    inputs = {
        "normal_key": "normal_value",
        "api_key": "secret_api_key",
        "openai_api_key": "secret_openai_api_key",
        "nested_api_key": {"api_key": "nested_secret"},
    }

    cleaned_inputs = TracingService._cleanup_inputs(inputs)

    # Verify values for keys containing api_key are replaced with *****
    assert cleaned_inputs["normal_key"] == "normal_value"
    assert cleaned_inputs["api_key"] == "*****"
    assert cleaned_inputs["openai_api_key"] == "*****"

    # Verify values for keys containing api_key are replaced with *****, even in nested dicts
    assert cleaned_inputs["nested_api_key"] == "*****"

    # Verify original input is not modified
    assert inputs["api_key"] == "secret_api_key"
    assert inputs["openai_api_key"] == "secret_openai_api_key"


@pytest.mark.asyncio
async def test_cleanup_inputs_masks_password_keyword():
    """Test that keys containing 'password' are masked."""
    inputs = {
        "password": "my-secret-password",  # pragma: allowlist secret
        "db_password": "db-secret",  # pragma: allowlist secret
        "normal_key": "visible",
    }

    cleaned = TracingService._cleanup_inputs(inputs)

    assert cleaned["password"] == "*****"  # noqa: S105
    assert cleaned["db_password"] == "*****"  # noqa: S105
    assert cleaned["normal_key"] == "visible"


@pytest.mark.asyncio
async def test_cleanup_inputs_masks_server_url_keyword():
    """Test that keys containing 'server_url' are masked."""
    inputs = {
        "server_url": "http://internal-server:8080",
        "my_server_url": "http://other-server",
        "public_url": "http://public.example.com",
    }

    cleaned = TracingService._cleanup_inputs(inputs)

    assert cleaned["server_url"] == "*****"
    assert cleaned["my_server_url"] == "*****"
    assert cleaned["public_url"] == "http://public.example.com"


@pytest.mark.asyncio
async def test_cleanup_inputs_handles_list_of_dicts():
    """Test that lists containing dicts are recursively cleaned."""
    inputs = {
        "items": [
            {"api_key": "secret1", "name": "item1"},  # pragma: allowlist secret
            {"password": "secret2", "value": "data"},  # pragma: allowlist secret
            "plain_string",
        ]
    }

    cleaned = TracingService._cleanup_inputs(inputs)

    items = cleaned["items"]
    assert items[0]["api_key"] == "*****"
    assert items[0]["name"] == "item1"
    assert items[1]["password"] == "*****"  # noqa: S105
    assert items[1]["value"] == "data"
    assert items[2] == "plain_string"


@pytest.mark.asyncio
async def test_cleanup_inputs_handles_nested_list_in_dict():
    """Test that nested lists inside dicts are recursively cleaned."""
    inputs = {
        "config": {
            "credentials": [
                {"api_key": "nested-secret"},  # pragma: allowlist secret
            ]
        }
    }

    cleaned = TracingService._cleanup_inputs(inputs)

    assert cleaned["config"]["credentials"][0]["api_key"] == "*****"


@pytest.mark.asyncio
async def test_cleanup_inputs_does_not_mutate_original():
    """Test that the original input dict is not modified."""
    inputs = {
        "password": "original-password",  # pragma: allowlist secret
        "server_url": "http://original-url",
    }
    original_password = inputs["password"]
    original_url = inputs["server_url"]

    TracingService._cleanup_inputs(inputs)

    assert inputs["password"] == original_password
    assert inputs["server_url"] == original_url


@pytest.mark.asyncio
async def test_cleanup_inputs_empty_dict():
    """Test that empty dict is handled gracefully."""
    cleaned = TracingService._cleanup_inputs({})
    assert cleaned == {}


@pytest.mark.asyncio
async def test_start_tracers_with_exception(tracing_service):
    """Test starting tracers with exception handling."""
    run_id = uuid.uuid4()
    run_name = "test_run"
    user_id = "test_user"
    session_id = "test_session"
    project_name = "test_project"

    # Mock _initialize_langsmith_tracer to raise exception
    with (
        patch.object(
            tracing_service,
            "_initialize_langsmith_tracer",
            side_effect=Exception("Mock exception"),
        ),
        patch("langflow.services.tracing.service.logger") as mock_logger,
    ):
        # Configure async mock method
        mock_logger.adebug = AsyncMock()

        # start_tracers should return normally even with exception
        await tracing_service.start_tracers(run_id, run_name, user_id, session_id, project_name)

        # Verify exception was logged
        mock_logger.adebug.assert_any_call("Error initializing tracers: Mock exception")

        # Verify trace_context was set even with exception
        trace_context = trace_context_var.get()
        assert trace_context is not None
        assert trace_context.run_id == run_id
        assert trace_context.run_name == run_name

        # Cleanup
        await tracing_service.end_tracers({})


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_tracers")
async def test_trace_worker_with_exception(tracing_service):
    """Test trace worker exception handling."""
    run_id = uuid.uuid4()
    run_name = "test_run"
    user_id = "test_user"
    session_id = "test_session"
    project_name = "test_project"

    # Create a trace function that raises an exception
    def failing_trace_func():
        msg = "Mock trace function exception"
        raise ValueError(msg)

    with patch("langflow.services.tracing.service.logger") as mock_logger:
        # Configure async mock method
        mock_logger.aexception = AsyncMock()

        # Remove incorrect context manager usage
        await tracing_service.start_tracers(run_id, run_name, user_id, session_id, project_name)

        # Get trace_context and add failing trace function to queue
        trace_context = trace_context_var.get()
        await trace_context.traces_queue.put((failing_trace_func, ()))

        # Wait for async queue processing
        await asyncio.sleep(0.1)

        # Verify exception was logged
        mock_logger.aexception.assert_called_with("Error processing trace_func")

        # Cleanup
        await tracing_service.end_tracers({})


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_tracers")
async def test_concurrent_tracing(tracing_service, mock_component):
    """Test two tasks running start_tracers concurrently, with each task running 2 concurrent trace_component tasks."""

    # Define common task function: start tracers and run two component traces
    async def run_task(
        run_id,
        run_name,
        user_id,
        session_id,
        project_name,
        inputs,
        metadata,
        task_prefix,
        sleep_duration=0.1,
    ):
        await tracing_service.start_tracers(run_id, run_name, user_id, session_id, project_name)

        async def run_component_task(component, trace_name, component_suffix):
            async with tracing_service.trace_component(component, trace_name, inputs, metadata) as ts:
                ts.add_log(trace_name, {"message": f"{task_prefix} {component_suffix} log"})
                outputs = {"output_key": f"{task_prefix}_{component_suffix}_output"}
                await asyncio.sleep(sleep_duration)
                ts.set_outputs(trace_name, outputs)

        task1 = asyncio.create_task(run_component_task(mock_component, f"{run_id} trace_name1", f"{run_id} component1"))
        task2 = asyncio.create_task(run_component_task(mock_component, f"{run_id} trace_name2", f"{run_id} component2"))
        await asyncio.gather(task1, task2)

        await tracing_service.end_tracers({"final_output": f"{task_prefix}_final_output"})
        trace_context = trace_context_var.get()
        return trace_context.tracers["langfuse"]

    inputs1 = {"input_key": "input_value1"}
    metadata1 = {"metadata_key": "metadata_value1"}
    inputs2 = {"input_key": "input_value2"}
    metadata2 = {"metadata_key": "metadata_value2"}

    task1 = asyncio.create_task(
        run_task(
            "run_id1",
            "run_name1",
            "user_id1",
            "session_id1",
            "project_name1",
            inputs1,
            metadata1,
            "task1",
            2,
        )
    )
    await asyncio.sleep(0.1)
    task2 = asyncio.create_task(
        run_task(
            "run_id2",
            "run_name2",
            "user_id2",
            "session_id2",
            "project_name2",
            inputs2,
            metadata2,
            "task2",
            0.1,
        )
    )
    tracer1 = await task1
    tracer2 = await task2

    # Verify tracer1 and tracer2 have correct trace data
    assert tracer1.trace_name == "run_name1"
    assert tracer1.project_name == "project_name1"
    assert tracer1.user_id == "user_id1"
    assert tracer1.session_id == "session_id1"
    assert dict(tracer1.outputs_param.get("run_id1 trace_name1")) == {"output_key": "task1_run_id1 component1_output"}
    assert dict(tracer1.outputs_param.get("run_id1 trace_name2")) == {"output_key": "task1_run_id1 component2_output"}

    assert tracer2.trace_name == "run_name2"
    assert tracer2.project_name == "project_name2"
    assert tracer2.user_id == "user_id2"
    assert tracer2.session_id == "session_id2"
    assert dict(tracer2.outputs_param.get("run_id2 trace_name1")) == {"output_key": "task2_run_id2 component1_output"}
    assert dict(tracer2.outputs_param.get("run_id2 trace_name2")) == {"output_key": "task2_run_id2 component2_output"}


def test_add_log_without_component_context(tracing_service):
    """add_log should log debug and return (not raise) when component context is missing."""
    # Ensure no component context is set
    component_context_var.set(None)
    # Should not raise
    tracing_service.add_log("some_trace", {"message": "test"})


def test_set_outputs_without_component_context(tracing_service):
    """set_outputs should log debug and return (not raise) when component context is missing."""
    # Ensure no component context is set
    component_context_var.set(None)
    # Should not raise
    tracing_service.set_outputs("some_trace", {"key": "value"})


@pytest.mark.asyncio
async def test_otlp_tracer_with_valid_endpoint():
    """Test OTLP tracer initialization with valid endpoint."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
        clear=True,
    ):
        test_trace_id = uuid.uuid4()
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=test_trace_id,
            user_id="test_user",
            session_id="test_session",
        )
        assert tracer.ready is True
        assert tracer.tracer is not None
        assert tracer.root_span is not None
        assert tracer.root_span.name == "test_trace"
        assert tracer.root_span.is_recording()
        # Verify trace context propagation carrier
        assert tracer.carrier != {}
        assert "traceparent" in tracer.carrier
        # Verify traceparent contains valid trace_id from root span
        parts = tracer.carrier["traceparent"].split("-")
        assert len(parts) == 4
        assert parts[1] == format(tracer.root_span.context.trace_id, "032x")
        tracer.close()


@pytest.mark.asyncio
async def test_otlp_tracer_with_generic_endpoint():
    """Test OTLP tracer initialization with generic OTEL_EXPORTER_OTLP_ENDPOINT."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict("os.environ", {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"}, clear=True):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is True
        assert tracer.tracer is not None


@pytest.mark.asyncio
async def test_otlp_tracer_without_endpoint():
    """Test OTLP tracer fails gracefully when no endpoint is configured."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict("os.environ", {}, clear=True):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is False


@pytest.mark.asyncio
async def test_otlp_tracer_protocol_http_protobuf():
    """Test OTLP tracer with HTTP protobuf protocol."""
    from langflow.services.tracing.otlp import OTLPTracer

    with (
        patch.dict(
            "os.environ",
            {
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            },
            clear=True,
        ),
        patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter") as mock_http_exporter,
    ):
        mock_http_exporter.return_value = MagicMock()

        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is True
        # Verify HTTP exporter was used
        mock_http_exporter.assert_called_once()


@pytest.mark.asyncio
async def test_otlp_tracer_protocol_grpc():
    """Test OTLP tracer with gRPC protocol."""
    from langflow.services.tracing.otlp import OTLPTracer

    with (
        patch.dict(
            "os.environ",
            {
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4317",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
            },
            clear=True,
        ),
        patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter") as mock_grpc_exporter,
    ):
        mock_grpc_exporter.return_value = MagicMock()

        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is True
        # Verify gRPC exporter was used
        mock_grpc_exporter.assert_called_once()


@pytest.mark.asyncio
async def test_otlp_tracer_service_name():
    """Test OTLP tracer respects OTEL_SERVICE_NAME."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict(
        "os.environ",
        {
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces",
            "OTEL_SERVICE_NAME": "custom-service",
        },
        clear=True,
    ):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is True
        # Verify service name in resource attributes via the shared provider
        from langflow.services.tracing import otlp as otlp_mod

        assert otlp_mod._shared_provider.resource.attributes["service.name"] == "custom-service"


@pytest.mark.asyncio
async def test_otlp_tracer_resource_attributes():
    """Test OTLP tracer includes resource attributes from environment."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict(
        "os.environ",
        {
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces",
            "OTEL_RESOURCE_ATTRIBUTES": "environment=production,version=1.0",
        },
        clear=True,
    ):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is True
        # Verify resource attributes were parsed and included
        from langflow.services.tracing import otlp as otlp_mod

        resource_attrs = otlp_mod._shared_provider.resource.attributes
        assert resource_attrs["environment"] == "production"
        assert resource_attrs["version"] == "1.0"
        assert resource_attrs["langflow.project_name"] == "test_project"


@pytest.mark.asyncio
async def test_otlp_tracer_add_and_end_trace():
    """Test OTLP tracer add_trace and end_trace methods."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
        clear=True,
    ):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )

        trace_id = "test_child_trace_id"
        inputs = {"input_key": "input_value"}
        outputs = {"output_key": "output_value"}

        # Add trace
        tracer.add_trace(
            trace_id=trace_id,
            trace_name="child_trace",
            trace_type="component",
            inputs=inputs,
            metadata={"meta_key": "meta_value"},
        )

        assert trace_id in tracer.child_spans

        # Verify span attributes were set
        child_span = tracer.child_spans[trace_id]
        assert child_span.name == "child_trace"
        # Note: attributes are set but not easily accessible from the span object
        # The span.attributes property is internal and may not be directly testable

        # End trace
        tracer.end_trace(
            trace_id=trace_id,
            trace_name="child_trace",
            outputs=outputs,
        )

        assert trace_id not in tracer.child_spans


@pytest.mark.asyncio
async def test_otlp_tracer_end_with_error():
    """Test OTLP tracer end method with error."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
        clear=True,
    ):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )

        # Mock record_exception to verify it's called
        tracer.root_span.record_exception = MagicMock()

        test_error = ValueError("Test error")
        tracer.end(
            inputs={"input_key": "input_value"},
            outputs={"output_key": "output_value"},
            error=test_error,
        )

        # Verify the tracer handled the error without raising
        assert tracer.ready is True
        # Verify exception was recorded
        tracer.root_span.record_exception.assert_called_once_with(test_error)


@pytest.mark.asyncio
async def test_otlp_tracer_child_trace_with_error():
    """Test OTLP tracer end_trace method with error."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
        clear=True,
    ):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )

        trace_id = "test_child_trace_id"

        # Add trace
        tracer.add_trace(
            trace_id=trace_id,
            trace_name="child_trace",
            trace_type="component",
            inputs={"input_key": "input_value"},
        )

        # Mock record_exception
        child_span = tracer.child_spans[trace_id]
        child_span.record_exception = MagicMock()

        # End trace with error
        test_error = ValueError("Child trace error")
        tracer.end_trace(
            trace_id=trace_id,
            trace_name="child_trace",
            error=test_error,
        )

        # Verify exception was recorded
        child_span.record_exception.assert_called_once_with(test_error)


@pytest.mark.asyncio
async def test_otlp_tracer_close_is_noop():
    """Test OTLP tracer close() is a no-op (provider lifecycle is module-level)."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
        clear=True,
    ):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )

        # close() should not raise and should be a no-op
        tracer.close()
        assert tracer.ready is True


@pytest.mark.asyncio
async def test_otlp_shutdown_provider():
    """Test shutdown_otlp_provider flushes and clears the shared provider."""
    from langflow.services.tracing import otlp as otlp_mod
    from langflow.services.tracing.otlp import OTLPTracer, shutdown_otlp_provider

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
        clear=True,
    ):
        OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert otlp_mod._shared_provider is not None

        shutdown_otlp_provider()

        assert otlp_mod._shared_provider is None
        assert otlp_mod._shared_tracer is None


@pytest.mark.asyncio
async def test_otlp_tracer_not_ready_operations():
    """Test that OTLP tracer operations are no-ops when not ready."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict("os.environ", {}, clear=True):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is False

        # These should not raise exceptions
        tracer.add_trace(
            trace_id="test_id",
            trace_name="test_name",
            trace_type="test_type",
            inputs={"key": "value"},
        )

        tracer.end_trace(
            trace_id="test_id",
            trace_name="test_name",
            outputs={"key": "value"},
        )

        tracer.end(
            inputs={"key": "value"},
            outputs={"key": "value"},
        )

        # Verify tracer remains not ready after all operations
        assert tracer.ready is False


@pytest.mark.asyncio
async def test_otlp_tracer_setup_failure():
    """Test OTLP tracer handles setup failures gracefully."""
    from langflow.services.tracing.otlp import OTLPTracer

    with (
        patch.dict(
            "os.environ",
            {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
            clear=True,
        ),
        patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter") as mock_exporter,
    ):
        # Make the exporter instantiation fail
        mock_exporter.side_effect = Exception("Connection refused")

        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        # Tracer should not be ready when setup fails
        assert tracer.ready is False


@pytest.mark.asyncio
async def test_otlp_tracer_optional_params():
    """Test OTLP tracer with optional user_id and session_id."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
        clear=True,
    ):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
            # user_id and session_id are omitted
        )
        assert tracer.ready is True
        assert tracer.user_id is None
        assert tracer.session_id is None


@pytest.mark.asyncio
async def test_otlp_tracer_span_attributes():
    """Test that OTLP tracer sets correct span attributes."""
    from langflow.services.tracing.otlp import OTLPTracer

    # Create a mock exporter to capture spans
    class SpanCapturingExporter:
        """In-memory span exporter that records exported spans for test assertions."""

        def __init__(self):
            self.exported_spans = []

        def export(self, spans):
            """Append finished spans to the internal list."""
            self.exported_spans.extend(spans)
            return MagicMock()

        def shutdown(self):
            """No-op shutdown."""

        def force_flush(self, _timeout_millis=None):
            """No-op flush; all spans are already stored synchronously."""
            return True

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
        clear=True,
    ):
        # Patch the OTLPSpanExporter to use our capturing exporter instead
        span_exporter = SpanCapturingExporter()
        with patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter") as mock_exporter:
            mock_exporter.return_value = span_exporter

            test_trace_id = uuid.uuid4()
            tracer = OTLPTracer(
                trace_name="test_trace",
                trace_type="chain",
                project_name="test_project",
                trace_id=test_trace_id,
                user_id="test_user",
                session_id="test_session",
            )

            # Add a child trace
            tracer.add_trace(
                trace_id="child_1",
                trace_name="child_trace",
                trace_type="component",
                inputs={"input_key": "input_value"},
                metadata={"meta_key": "meta_value"},
            )

            # End the child trace
            tracer.end_trace(
                trace_id="child_1",
                trace_name="child_trace",
                outputs={"output_key": "output_value"},
            )

            # End the root trace
            tracer.end(
                inputs={"root_input": "value"},
                outputs={"root_output": "value"},
            )

            # Force flush to export spans
            from langflow.services.tracing import otlp as otlp_mod

            otlp_mod._shared_provider.force_flush()

            # Verify spans were exported
            assert len(span_exporter.exported_spans) == 2  # root + child

            # Find the root span
            root_spans = [s for s in span_exporter.exported_spans if s.name == "test_trace"]
            assert len(root_spans) == 1
            root_span = root_spans[0]

            # Verify root span attributes
            assert root_span.attributes["langflow.trace_id"] == str(test_trace_id)
            assert root_span.attributes["langflow.trace_name"] == "test_trace"
            assert root_span.attributes["langflow.trace_type"] == "chain"
            assert root_span.attributes["langflow.project_name"] == "test_project"
            assert root_span.attributes["langflow.user_id"] == "test_user"
            assert root_span.attributes["langflow.session_id"] == "test_session"

            # Find the child span
            child_spans = [s for s in span_exporter.exported_spans if s.name == "child_trace"]
            assert len(child_spans) == 1
            child_span = child_spans[0]

            # Verify child span attributes
            assert child_span.attributes["trace_id"] == "child_1"
            assert child_span.attributes["trace_name"] == "child_trace"
            assert child_span.attributes["trace_type"] == "component"
            assert "inputs" in child_span.attributes
            assert "outputs" in child_span.attributes

            # Verify parent-child relationship via trace IDs
            root_trace_id = format(root_span.context.trace_id, "032x")
            child_trace_id = format(child_span.context.trace_id, "032x")
            assert child_trace_id == root_trace_id, (
                f"Child trace_id {child_trace_id} should match root trace_id {root_trace_id}"
            )

            # Child span's parent should be the root span
            assert child_span.parent is not None, "Child span should have a parent"
            child_parent_span_id = format(child_span.parent.span_id, "016x")
            root_span_id = format(root_span.context.span_id, "016x")
            assert child_parent_span_id == root_span_id, (
                f"Child parent span_id {child_parent_span_id} should match root span_id {root_span_id}"
            )

            # Verify outputs are JSON-encoded strings
            import json

            root_outputs = json.loads(root_span.attributes["outputs"])
            assert root_outputs["root_output"] == "value"
            child_outputs = json.loads(child_span.attributes["outputs"])
            assert child_outputs["output_key"] == "output_value"
            child_inputs = json.loads(child_span.attributes["inputs"])
            assert child_inputs["input_key"] == "input_value"


@pytest.mark.asyncio
async def test_otlp_tracer_missing_both_endpoints():
    """Test OTLP tracer is not ready when neither endpoint env var is set."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict("os.environ", {}, clear=True):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is False
        assert tracer.root_span is None
        assert tracer.tracer is None


@pytest.mark.asyncio
async def test_otlp_tracer_generic_endpoint_fallback():
    """Test OTLP tracer works with OTEL_EXPORTER_OTLP_ENDPOINT (generic) when traces-specific is absent."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"},
        clear=True,
    ):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is True
        assert tracer.root_span is not None
        tracer.close()


@pytest.mark.asyncio
async def test_otlp_tracer_traces_protocol_overrides_generic():
    """Test OTEL_EXPORTER_OTLP_TRACES_PROTOCOL takes priority over OTEL_EXPORTER_OTLP_PROTOCOL."""
    from langflow.services.tracing.otlp import OTLPTracer

    with (
        patch.dict(
            "os.environ",
            {
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4317",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "grpc",
            },
            clear=True,
        ),
        patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter") as mock_grpc,
    ):
        mock_grpc.return_value = MagicMock()

        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is True
        # gRPC exporter should be used despite generic protocol saying http/protobuf
        mock_grpc.assert_called_once()


@pytest.mark.asyncio
async def test_otlp_tracer_unsupported_protocol_falls_back():
    """Test OTLP tracer falls back to http/protobuf for unsupported protocol values (including http/json)."""
    from langflow.services.tracing.otlp import OTLPTracer

    for bad_protocol in ("invalid_protocol", "http/json"):
        with patch.dict(
            "os.environ",
            {
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces",
                "OTEL_EXPORTER_OTLP_PROTOCOL": bad_protocol,
            },
            clear=True,
        ):
            tracer = OTLPTracer(
                trace_name="test_trace",
                trace_type="chain",
                project_name="test_project",
                trace_id=uuid.uuid4(),
            )
            assert tracer.ready is True, f"Tracer should fall back gracefully for protocol={bad_protocol}"
            tracer.close()


@pytest.mark.asyncio
async def test_otlp_tracer_setup_exception_types():
    """Test OTLP tracer catches various exception types during setup."""
    from langflow.services.tracing.otlp import OTLPTracer

    for exc_cls in (RuntimeError, ConnectionError, OSError, TypeError):
        with (
            patch.dict(
                "os.environ",
                {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
                clear=True,
            ),
            patch(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                side_effect=exc_cls("setup failed"),
            ),
        ):
            tracer = OTLPTracer(
                trace_name="test_trace",
                trace_type="chain",
                project_name="test_project",
                trace_id=uuid.uuid4(),
            )
            assert tracer.ready is False, f"Tracer should not be ready after {exc_cls.__name__}"


@pytest.mark.asyncio
async def test_otlp_tracer_end_trace_unknown_id():
    """Test that ending a trace with an unknown ID is a safe no-op."""
    from langflow.services.tracing.otlp import OTLPTracer

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
        clear=True,
    ):
        tracer = OTLPTracer(
            trace_name="test_trace",
            trace_type="chain",
            project_name="test_project",
            trace_id=uuid.uuid4(),
        )
        assert tracer.ready is True

        # Ending a non-existent child trace should not raise
        tracer.end_trace(
            trace_id="nonexistent_id",
            trace_name="nonexistent",
            outputs={"key": "value"},
        )

        # Tracer should still be functional
        assert tracer.ready is True
        tracer.close()


@pytest.mark.asyncio
async def test_otlp_tracer_nested_metadata_stringified():
    """Test that nested dicts/lists in metadata are JSON-stringified for span attributes."""
    from langflow.services.tracing.otlp import OTLPTracer

    class SpanCapturingExporter:
        """In-memory span exporter that records exported spans for test assertions."""

        def __init__(self):
            self.exported_spans = []

        def export(self, spans):
            """Append finished spans to the internal list."""
            self.exported_spans.extend(spans)
            return MagicMock()

        def shutdown(self):
            """No-op shutdown."""

        def force_flush(self, _timeout_millis=None):
            """No-op flush; all spans are already stored synchronously."""
            return True

    with patch.dict(
        "os.environ",
        {"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://localhost:4318/v1/traces"},
        clear=True,
    ):
        span_exporter = SpanCapturingExporter()
        with patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter") as mock_exp:
            mock_exp.return_value = span_exporter

            tracer = OTLPTracer(
                trace_name="test_trace",
                trace_type="chain",
                project_name="test_project",
                trace_id=uuid.uuid4(),
            )

            nested_metadata = {
                "simple_key": "simple_value",
                "nested_dict": {"inner_key": "inner_value", "deep": {"a": 1}},
                "nested_list": [1, {"b": 2}, [3, 4]],
                "number": 42,
            }

            # Test via add_trace (child span metadata)
            tracer.add_trace(
                trace_id="child_1",
                trace_name="child",
                trace_type="component",
                inputs={"x": "y"},
                metadata=nested_metadata,
            )
            tracer.end_trace(trace_id="child_1", trace_name="child")

            # Test via end() (root span metadata)
            tracer.end(
                inputs={},
                outputs={},
                metadata=nested_metadata,
            )

            from langflow.services.tracing import otlp as otlp_mod

            otlp_mod._shared_provider.force_flush()

            import json

            # Verify child span metadata attributes
            child_span = next(s for s in span_exporter.exported_spans if s.name == "child")
            assert child_span.attributes["metadata.simple_key"] == "simple_value"
            assert child_span.attributes["metadata.number"] == 42
            # Nested dict should be JSON-stringified
            parsed_dict = json.loads(child_span.attributes["metadata.nested_dict"])
            assert parsed_dict["inner_key"] == "inner_value"
            assert parsed_dict["deep"]["a"] == 1
            # Nested list should be JSON-stringified
            parsed_list = json.loads(child_span.attributes["metadata.nested_list"])
            assert parsed_list == [1, {"b": 2}, [3, 4]]

            # Verify root span metadata attributes
            root_span = next(s for s in span_exporter.exported_spans if s.name == "test_trace")
            assert root_span.attributes["metadata.simple_key"] == "simple_value"
            assert root_span.attributes["metadata.number"] == 42
            parsed_dict = json.loads(root_span.attributes["metadata.nested_dict"])
            assert parsed_dict["deep"]["a"] == 1
