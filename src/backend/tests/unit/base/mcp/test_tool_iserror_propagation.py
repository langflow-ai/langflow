"""MCP tool wrappers must raise on CallToolResult.isError — for EVERY caller.

The per-component check in ``MCPToolsComponent.build_output`` only exists in freshly
added nodes: saved flows freeze the component code, so an older canvas node happily
turns a FAILED tool call (isError=True, e.g. the HITL guard) into a successful
DataFrame. ``create_tool_coroutine`` / ``create_tool_func`` are package code — never
frozen — and both the component build and the agent tool path flow through them, so
enforcing isError here covers old saved flows and stops agents from reading the error
text as a valid tool result.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from lfx.base.mcp.util import create_tool_coroutine
from pydantic import BaseModel


class _ArgSchema(BaseModel):
    input_value: str = ""


def _result(*, is_error: bool, text: str = "ok") -> SimpleNamespace:
    return SimpleNamespace(
        isError=is_error,
        content=[SimpleNamespace(type="text", text=text)],
    )


class _StubClient:
    def __init__(self, result):
        self._result = result

    async def run_tool(self, _tool_name, arguments):  # noqa: ARG002
        return self._result


HITL_TEXT = "This flow uses Human-in-the-Loop and cannot pause on this path."


async def test_coroutine_raises_on_iserror_result():
    client = _StubClient(_result(is_error=True, text=HITL_TEXT))
    coroutine = create_tool_coroutine("hitl_component", _ArgSchema, client)

    with pytest.raises(ValueError, match="Human-in-the-Loop") as excinfo:
        await coroutine(input_value="hi")

    assert "hitl_component" in str(excinfo.value)


async def test_coroutine_returns_success_result_unchanged():
    ok = _result(is_error=False, text="all good")
    client = _StubClient(ok)
    coroutine = create_tool_coroutine("some_tool", _ArgSchema, client)

    assert await coroutine(input_value="hi") is ok


async def test_coroutine_handles_result_without_iserror_attr():
    # Defensive: a server/library variant lacking the attribute must not crash.
    bare = SimpleNamespace(content=[SimpleNamespace(type="text", text="fine")])
    client = _StubClient(bare)
    coroutine = create_tool_coroutine("some_tool", _ArgSchema, client)

    assert await coroutine(input_value="hi") is bare
