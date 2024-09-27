from typing import Any
from uuid import UUID

from langchain.callbacks.base import AsyncCallbackHandler
from langchain_core.agents import AgentAction, AgentFinish

from langflow.schema.log import LogFunctionType


class AgentAsyncHandler(AsyncCallbackHandler):
    """Async callback handler that can be used to handle callbacks from langchain."""

    def __init__(self, log_function: LogFunctionType | None = None):
        self.log_function = log_function

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if self.log_function is None:
            return
        self.log_function(
            {
                "type": "tool_start",
                "serialized": serialized,
                "input_str": input_str,
                "run_id": run_id,
                "parent_run_id": parent_run_id,
                "tags": tags,
                "metadata": metadata,
                "inputs": inputs,
                **kwargs,
            },
            name="Tool Start",
        )

    async def on_tool_end(self, output: Any, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> None:
        if self.log_function is None:
            return
        self.log_function(
            {
                "type": "tool_end",
                "output": output,
                "run_id": run_id,
                "parent_run_id": parent_run_id,
                **kwargs,
            },
            name="Tool End",
        )

    async def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if self.log_function is None:
            return
        self.log_function(
            {
                "type": "agent_action",
                "action": action,
                "run_id": run_id,
                "parent_run_id": parent_run_id,
                "tags": tags,
                **kwargs,
            },
            name="Agent Action",
        )

    async def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if self.log_function is None:
            return
        self.log_function(
            {
                "type": "agent_finish",
                "finish": finish,
                "run_id": run_id,
                "parent_run_id": parent_run_id,
                "tags": tags,
                **kwargs,
            },
            name="Agent Finish",
        )
