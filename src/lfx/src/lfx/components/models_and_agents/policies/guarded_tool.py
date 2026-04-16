import json

from langchain_core.messages import ToolCall
from toolguard.runtime import PolicyViolationException
from toolguard.runtime.runtime import ToolguardRuntime

from lfx.components.models_and_agents.policies.tool_invoker import ToolInvoker
from lfx.field_typing import Tool
from lfx.log.logger import logger


class GuardedTool(Tool):
    """A tool wrapper that applies ToolGuard policy validation before execution.

    This component requires async execution as ToolGuard operates asynchronously.
    The synchronous `run()` method is not supported and will raise NotImplementedError.
    Always use `arun()` or async invocation methods.
    """

    _orig_tool: Tool
    _tool_invoker: ToolInvoker
    _toolguard: ToolguardRuntime

    def __init__(self, tool: Tool, all_tools: list[Tool], toolguard: ToolguardRuntime):
        super().__init__(
            name=tool.name,
            description=tool.description,
            args_schema=getattr(tool, "args_schema", None),
            return_direct=getattr(tool, "return_direct", False),
            func=self.run,
            coroutine=self.arun,
            tags=tool.tags,
            metadata=tool.metadata,
            verbose=True,
        )
        self._orig_tool = tool
        self._tool_invoker = ToolInvoker(all_tools)
        self._toolguard = toolguard

    @property
    def args(self) -> dict:
        return self._orig_tool.args

    def _parse_string_to_dict(self, value: str) -> dict:
        """Parse a string as JSON, or wrap it in a dict if parsing fails."""
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"input": value}

    def parse_input(self, tool_input: str | dict | ToolCall) -> dict:
        # Handle string input - try to parse as JSON, fallback to wrapped input
        if isinstance(tool_input, str):
            return self._parse_string_to_dict(tool_input)

        # Handle ToolCall dict format - extract and parse args
        if isinstance(tool_input, dict) and "args" in tool_input:
            args = tool_input["args"]
            if isinstance(args, str):
                return self._parse_string_to_dict(args)
            return args if isinstance(args, dict) else {}

        # Return dict as-is or empty dict for None/other types
        return tool_input if isinstance(tool_input, dict) else {}

    def run(self, tool_input: str | dict | ToolCall, config=None, **kwargs):
        """Synchronous execution is not supported for GuardedTool.

        ToolGuard requires async execution for policy validation. Please use the
        async version `arun()` instead, or ensure your execution context supports
        async tool invocation.

        Raises:
            NotImplementedError: Always raised as sync execution is not supported.
        """
        msg = (
            "GuardedTool does not support synchronous execution. "
            "ToolGuard requires async execution for policy validation. "
            "Please use `arun()` instead or ensure your execution context supports async tool invocation."
        )
        raise NotImplementedError(msg)

    async def arun(self, tool_input: str | dict | ToolCall, config=None, **kwargs):
        args = self.parse_input(tool_input)
        logger.debug(f"running toolguard for {self.name}")

        with self._toolguard:
            try:
                await self._toolguard.guard_toolcall(self.name, args=args, delegate=self._tool_invoker)
                return await self._orig_tool.arun(tool_input=args, config=config, **kwargs)
            except PolicyViolationException as ex:
                logger.debug(f"exception: {ex.message}")
                return {
                    "ok": False,
                    "error": {
                        "type": "PolicyViolationException",
                        "code": "FAILURE",
                        "message": ex.message,
                        "retryable": True,
                    },
                }
            except Exception:
                logger.exception("Unhandled exception in class GuardedTool.arun()")
                raise
