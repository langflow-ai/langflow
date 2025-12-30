import json
from typing import Any, TypeVar

from pydantic import BaseModel
from toolguard import IToolInvoker, load_toolguards
from mcp.types import CallToolResult
from lfx.field_typing import Tool
from lfx.field_typing.constants import BaseTool
from lfx.log.logger import logger

class GuardedTool(Tool):
    _orig_tool: Tool
    _tool_invoker: IToolInvoker
    _tg_dir: str

    def __init__(self, tool: Tool, all_tools: list[Tool], tg_dir: str):
        super().__init__(
            name=tool.name,
            description=tool.description,
            args_schema=getattr(tool, "args_schema", None),
            return_direct=getattr(tool, "return_direct", False),
            func=self._run,
            coroutine=self._arun,
            tags=tool.tags,
            metadata=tool.metadata,
            verbose=True,
        )
        self._orig_tool = tool
        self._tool_invoker = ToolInvoker(all_tools)
        self._tg_dir = tg_dir

    @property
    def args(self) -> dict:
        return self._orig_tool.args

    def parse_input(self, tool_input: str | dict):
        if isinstance(tool_input, str):
            try:
                return json.loads(tool_input)
            except json.JSONDecodeError:
                return {"input": tool_input}
        else:
            return tool_input or {}

    def run(self, tool_input: str | dict, config=None, **kwargs):
        args = self.parse_input(tool_input)
        print(f"tool={self.name}, args={args}, config={config}, kwargs={kwargs}")
        with load_toolguards(self._tg_dir) as toolguard:
            from rt_toolguard.data_types import PolicyViolationException  # type: ignore

            try:
                toolguard.check_toolcall(self.name, args=args, delegate=self._tool_invoker)
                return self._orig_tool.run(args, config=config, **kwargs)
            except PolicyViolationException as ex:
                return f"Error: {ex.message}"
            except Exception as ex:
                logger.exception("Unhandled exception in WrappedTool._arun")
                raise ex

    async def arun(self, tool_input: str | dict, config=None, **kwargs):
        args = self.parse_input(tool_input)
        print(f"tool={self.name}, args={args}, config={config}, kwargs={kwargs}")
        with load_toolguards(self._tg_dir) as toolguard:
            from rt_toolguard.data_types import PolicyViolationException  # type: ignore

            try:
                toolguard.check_toolcall(self.name, args=args, delegate=self._tool_invoker)
                res = await self._orig_tool.arun(tool_input=args, config=config, **kwargs)
                return res
            except PolicyViolationException as ex:
                return f"Error: {ex.message}"
            except Exception as ex:
                logger.exception("Unhandled exception in WrappedTool._arun")
                raise ex

class ToolInvoker(IToolInvoker):
    T = TypeVar("T")
    _tools: dict[str, BaseTool]

    def __init__(self, tools: list[BaseTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def invoke(self, toolname: str, arguments: dict[str, Any], return_type: type[T]) -> T:
        tool = self._tools.get(toolname)
        if tool:
            res = tool.invoke(input=arguments)

            if isinstance(res, CallToolResult): #an MCP tool result
                res_dict = res.structuredContent['result']
            else: #component tool result
                res_dict = res["value"]

            if issubclass(return_type, BaseModel):
                return return_type.model_validate(res_dict)
            if return_type in (int, float, str, bool):
                return return_type(res_dict)
            return res_dict

        raise ValueError(f"unknown tool {toolname}")
