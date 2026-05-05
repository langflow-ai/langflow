"""Invoke an LLM via its native with_structured_output() interface."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel


async def invoke_with_native_structured_output(
    *,
    llm: Any,
    model_cls: type[BaseModel],
    system_prompt: str,
    input_value: str,
) -> dict[str, Any] | list[Any]:
    """Run llm.with_structured_output(model_cls) and return a JSON-serializable result."""
    runnable = llm.with_structured_output(model_cls)
    messages: list[Any] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=input_value))

    raw = await runnable.ainvoke(messages)
    return _to_jsonable(raw)


def _to_jsonable(value: Any) -> dict[str, Any] | list[Any]:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [item.model_dump() if isinstance(item, BaseModel) else item for item in value]
    if isinstance(value, dict):
        return value
    msg = f"Native structured output returned unsupported type: {type(value).__name__}"
    raise TypeError(msg)
