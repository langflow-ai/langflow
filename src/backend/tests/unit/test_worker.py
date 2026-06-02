from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from langflow import worker


def test_run_workflow_job_task_delegates_to_async_helper():
    """The Celery task should pass serialized inputs to the async workflow runner."""
    payload = {
        "job_id": "550e8400-e29b-41d4-a716-446655440001",
        "flow_id": "flow-123",
        "user_id": "user-123",
        "flow_name": "Background Flow",
        "graph_data": {"nodes": [], "edges": []},
        "tweaks": {"ChatInput-abc": {"input_value": "hello"}},
        "session_id": "session-123",
        "request_variables": {"x-langflow-global-var-token": "value"},
    }
    sync_runner = MagicMock()

    with patch("langflow.worker.async_to_sync", return_value=sync_runner) as mock_async_to_sync:
        worker.run_workflow_job.run(**payload)

    mock_async_to_sync.assert_called_once_with(worker._run_workflow_job)
    sync_runner.assert_called_once_with(**payload)


@pytest.mark.asyncio
async def test_run_workflow_job_reconstructs_graph_and_executes_with_status():
    """The worker should rebuild the Graph in-process before executing the job."""
    job_id = "550e8400-e29b-41d4-a716-446655440001"
    graph_data = {"nodes": [{"id": "ChatInput-abc"}], "edges": []}
    tweaks = {"ChatInput-abc": {"input_value": "hello"}}
    request_variables = {"x-langflow-global-var-token": "value"}
    processed_graph_data = {"nodes": [{"id": "ChatInput-abc", "data": {"input_value": "hello"}}], "edges": []}
    graph = MagicMock()
    graph.get_terminal_nodes.return_value = ["ChatOutput-def"]
    job_service = MagicMock()
    job_service.execute_with_status = AsyncMock()

    def fake_process_tweaks(data, received_tweaks, *, stream):
        assert data == graph_data
        assert data is not graph_data
        assert received_tweaks == tweaks
        assert stream is False
        data["mutated"] = True
        return processed_graph_data

    with (
        patch("langflow.processing.process.process_tweaks", side_effect=fake_process_tweaks),
        patch("lfx.graph.graph.base.Graph.from_payload", return_value=graph) as mock_from_payload,
        patch("langflow.services.deps.get_job_service", return_value=job_service),
    ):
        await worker._run_workflow_job(
            job_id=job_id,
            flow_id="flow-123",
            user_id="user-123",
            flow_name="Background Flow",
            graph_data=graph_data,
            tweaks=tweaks,
            session_id="session-123",
            request_variables=request_variables,
        )

    mock_from_payload.assert_called_once_with(
        processed_graph_data,
        flow_id="flow-123",
        user_id="user-123",
        flow_name="Background Flow",
        context={"request_variables": request_variables},
    )
    graph.set_run_id.assert_called_once_with(UUID(job_id))
    graph.get_terminal_nodes.assert_called_once_with()
    job_service.execute_with_status.assert_awaited_once()
    args, kwargs = job_service.execute_with_status.await_args
    assert args[0] == UUID(job_id)
    assert args[1].__name__ == "run_graph_internal"
    assert kwargs == {
        "graph": graph,
        "flow_id": "flow-123",
        "session_id": "session-123",
        "inputs": None,
        "outputs": ["ChatOutput-def"],
        "stream": False,
    }
    assert graph_data == {"nodes": [{"id": "ChatInput-abc"}], "edges": []}


def test_worker_tasks_have_docstrings():
    """Public worker tasks and helpers should stay documented."""
    assert worker.test_celery.__doc__
    assert worker.process_graph_cached_task.__doc__
    assert worker.run_workflow_job.__doc__
    assert worker._run_workflow_job.__doc__
