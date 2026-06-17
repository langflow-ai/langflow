from typing import Any, TypeVar

from langchain_core.messages import ToolMessage
from mcp.types import CallToolResult
from pydantic import BaseModel
from toolguard.runtime import IToolInvoker

from lfx.field_typing.constants import BaseTool
from lfx.log.logger import logger

T = TypeVar("T")


class ToolInvoker(IToolInvoker):
    _tools: dict[str, BaseTool]

    def __init__(self, tools: list[BaseTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    async def invoke(self, toolname: str, arguments: dict[str, Any], return_type: type[T]) -> T:
        tool = self._tools.get(toolname)
        if tool:
            logger.info(f"invoking {toolname} internally")
            res = await tool.ainvoke(input=arguments)

            # ToolInvoker calls ainvoke without tool_call_id, so MCPStructuredTool
            # returns the raw CallToolResult. The ToolMessage branch below is a
            # defensive fallback in case that ever changes.
            if isinstance(res, ToolMessage) and isinstance(res.artifact, CallToolResult):
                res_dict = res.artifact.structuredContent
            elif isinstance(res, CallToolResult):
                res_dict = res.structuredContent
            elif isinstance(res, list):
                # Multimodal content (e.g. images) — no structured extraction applies.
                return res  # type: ignore[return-value]
            elif isinstance(res, dict) and "value" in res:
                res_dict = res["value"]
            else:
                res_dict = res

            # Only try to extract "result" key if res_dict is a dictionary
            if isinstance(res_dict, dict):
                res_dict = res_dict.get("result", res_dict)

            if isinstance(res_dict, BaseModel):
                res_dict = res_dict.model_dump()

            if issubclass(return_type, BaseModel):
                return return_type.model_validate(res_dict)
            if return_type in (int, float, str, bool):
                return return_type(res_dict)
            return res_dict

        msg = f"unknown tool {toolname}"
        raise ValueError(msg)


# Made with Bob
