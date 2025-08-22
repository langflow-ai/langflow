import asyncio
import uuid
from unittest.mock import MagicMock, patch

import pytest
from langflow.services.settings.base import Settings
from langflow.services.settings.service import SettingsService
from langflow.services.tracing.base import BaseTracer
from langflow.services.tracing.service import (
    TracingService,
    component_context_var,
    trace_context_var,
)


class MockTracer(BaseTracer):
    def __init__(
        self,
        trace_name: str,
        trace_type: str,
        project_name: str,
        trace_id: uuid.UUID,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.trace_name = trace_name
        self.trace_type = trace_type
        self.project_name = project_name
        self.trace_id = trace_id
        self.user_id = user_id
        self.session_id = session_id
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
        inputs: dict[str, any],
        metadata: dict[str, any] | None = None,
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
        outputs: dict[str, any] | None = None,
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
        inputs: dict[str, any],
        outputs: dict[str, any],
        error: Exception | None = None,
        metadata: dict[str, any] | None = None,
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
    component._vertex = MagicMock()
    component._vertex.id = "test_vertex_id"
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
    assert "traceloop" in trace_context.tracers

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
        patch("langflow.services.tracing.service.logger.debug") as mock_logger,
    ):
        # start_tracers should return normally even with exception
        await tracing_service.start_tracers(run_id, run_name, user_id, session_id, project_name)

        # Verify exception was logged
        mock_logger.assert_any_call("Error initializing tracers: Mock exception")

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

    with patch("langflow.services.tracing.service.logger.exception") as mock_logger:
        # Remove incorrect context manager usage
        await tracing_service.start_tracers(run_id, run_name, user_id, session_id, project_name)

        # Get trace_context and add failing trace function to queue
        trace_context = trace_context_var.get()
        await trace_context.traces_queue.put((failing_trace_func, ()))

        # Wait for async queue processing
        await asyncio.sleep(0.1)

        # Verify exception was logged
        mock_logger.assert_called_with("Error processing trace_func")

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
        await task1
        task2 = asyncio.create_task(run_component_task(mock_component, f"{run_id} trace_name2", f"{run_id} component2"))
        await task2

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
