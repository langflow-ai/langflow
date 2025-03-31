import asyncio
from collections.abc import Awaitable, Callable

from langflow.helpers.base_model import BaseModel


def create_tool_coroutine(tool_name: str, arg_schema: type[BaseModel], session) -> Callable[[dict], Awaitable]:
    async def tool_coroutine(*args):
        if len(args) == 0:
            msg = f"at least one positional argument is required {args}"
            raise ValueError(msg)
        arg_dict = dict(zip(arg_schema.model_fields.keys(), args, strict=False))
        return await session.call_tool(tool_name, arguments=arg_dict)

    return tool_coroutine


def create_tool_func(tool_name: str, session) -> Callable[..., str]:
    def tool_func(**kwargs):
        if len(kwargs) == 0:
            msg = f"at least one named argument is required {kwargs}"
            raise ValueError(msg)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(session.call_tool(tool_name, arguments=kwargs))

    return tool_func
