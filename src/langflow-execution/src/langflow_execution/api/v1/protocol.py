from typing import Protocol

from fastapi import BackgroundTasks, Request

from langflow_execution.api.v1.schema.flow import Flow, FlowExecutionRequest


class FlowRunner(Protocol):
    async def run(
        self,
        *,
        background_tasks: BackgroundTasks,
        input_request: FlowExecutionRequest,
        stream: bool = False,
    ): ...

    async def webhook_run(
        self,
        flow: Flow,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict: ...
