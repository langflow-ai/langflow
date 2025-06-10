from typing import Protocol

from fastapi import BackgroundTasks, Request
from fastapi.responses import StreamingResponse

from langflow_execution.api.v1.schema.flow import Flow, FlowExecutionRequest, FlowExecutionResponse


# TODO: Define return types for all methods
class FlowRunner(Protocol):
    async def run(
        self,
        *,
        background_tasks: BackgroundTasks,
        input_request: FlowExecutionRequest,
        stream: bool = False,
    ) -> FlowExecutionResponse | StreamingResponse:
        """
        Execute a flow with the given input request.
        Args:
            background_tasks: FastAPI background task manager.
            input_request: The request containing flow execution parameters.
            stream: Whether to stream the response.
        Returns:
            The result of the flow execution (type depends on implementation).
        """
        ...

    async def webhook_run(
        self,
        flow: Flow,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict:
        """
        Execute a flow in response to a webhook request.
        Args:
            flow: The flow to execute.
            request: The incoming HTTP request.
            background_tasks: FastAPI background task manager.
        Returns:
            A dictionary with the status or result of the webhook execution.
        """
        ...

    async def describe(self, input_request: FlowExecutionRequest) -> dict:
        """
        Return a description of the flow, its structure, and requirements.
        Args:
            input_request: The request containing flow execution parameters.
        Returns:
            A dictionary describing the flow.
        """
        ...

    async def validate(self, input_request: FlowExecutionRequest) -> dict:
        """
        Validate the flow for correctness and completeness.
        Args:
            input_request: The request containing flow execution parameters.
        Returns:
            A dictionary with validation results and errors, if any.
        """
        ...

    async def stop(self, flow: Flow) -> dict:
        """
        Stop a running flow execution.
        Args:
            flow: The flow to stop.
        Returns:
            A dictionary with the status of the stop operation.
        """
        ...

    async def get_state(self, flow: Flow) -> dict:
        """
        Get the current state of a flow execution.
        Args:
            flow: The flow to query.
        Returns:
            A dictionary with the current state information.
        """
        ...
