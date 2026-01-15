import json
import traceback
from pathlib import Path
from typing import Any, TypeVar

from langchain_core.messages import ToolCall
from mcp.types import CallToolResult
from pydantic import BaseModel
from toolguard.runtime import IToolInvoker, PolicyViolationException, load_toolguards

from lfx.field_typing import Tool
from lfx.field_typing.constants import BaseTool
from lfx.log.logger import logger


class GuardedTool(Tool):
    _orig_tool: Tool
    _tool_invoker: IToolInvoker
    _tg_dir: Path

    def __init__(self, tool: Tool, all_tools: list[Tool], tg_dir: Path):
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

    def parse_input(self, tool_input: str | dict | ToolCall) -> dict:
        if isinstance(tool_input, str):
            try:
                return json.loads(tool_input)
            except json.JSONDecodeError:
                return {"input": tool_input}
        else:
            return tool_input or {}  # TODO: ToolCall

    def run(self, tool_input: str | dict | ToolCall, config=None, **kwargs):
        args = self.parse_input(tool_input)
        # print(f"tool={self.name}, args={args}, config={config}, kwargs={kwargs}")
        print(f'running toolguard for {self.name} with arguments {args}')

        with load_toolguards(self._tg_dir) as toolguard:
            try:
                toolguard.check_toolcall(self.name, args=args, delegate=self._tool_invoker)
                return self._orig_tool.run(tool_input=args, config=config, **kwargs)
            except PolicyViolationException as ex:
                return f"Error: {ex.message}"
            except Exception:
                logger.exception("Unhandled exception in GuardedTool.run()")
                traceback.print_exc()
                raise

    async def arun(self, tool_input: str | dict | ToolCall, config=None, **kwargs):
        args = self.parse_input(tool_input)
        # print(f"tool={self.name}, args={args}, config={config}, kwargs={kwargs}")
        print(f'running toolguard for {self.name} with arguments {args}')

        with load_toolguards(self._tg_dir) as toolguard:
            try:
                toolguard.check_toolcall(self.name, args=args, delegate=self._tool_invoker)
                return await self._orig_tool.arun(tool_input=args, config=config, **kwargs)
            except PolicyViolationException as ex:
                #print(f'exception: {ex.message}')
                return {
                    "ok": False,
                    "error": {
                        "type": "PolicyViolationException",
                        "code": "FAILURE",
                        "message": ex.message,
                        "retryable": True
                    }
                }
            except Exception:
                logger.exception("Unhandled exception in class GuardedTool.arun()")
                traceback.print_exc()
                raise


class ToolInvoker(IToolInvoker):
    T = TypeVar("T")
    _tools: dict[str, BaseTool]

    def __init__(self, tools: list[BaseTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def invoke(self, toolname: str, arguments: dict[str, Any], return_type: type[T]) -> T:
        tool = self._tools.get(toolname)
        if tool:
            res = tool.invoke(input=arguments)

            res_dict = res.structuredContent["result"] if isinstance(res, CallToolResult) else res["value"]
            if isinstance(res_dict, BaseModel):
                res_dict = res_dict.model_dump()

            if issubclass(return_type, BaseModel):
                return return_type.model_validate(res_dict)
            if return_type in (int, float, str, bool):
                return return_type(res_dict)
            return res_dict

        msg = f"unknown tool {toolname}"
        raise ValueError(msg)
