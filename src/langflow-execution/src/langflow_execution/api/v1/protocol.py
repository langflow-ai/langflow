from typing import Annotated, Depends, Protocol

from fastapi import BackgroundTasks, Depends, Request


class FlowRunner(Protocol):
    async def run(
        self,
        *,
        background_tasks: BackgroundTasks,
        flow: Annotated["FlowRead | None", Depends("get_flow_by_id_or_endpoint_name")],
        input_request: "SimplifiedAPIRequest | None" = None,
        stream: bool = False,
        api_key_user: Annotated["UserRead", Depends("api_key_security")],
    ): ...

    async def webhook_run(
        self,
        flow: "Flow",
        user: "User",
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict: ...
