"""A guarded external tool keeps its LangChain schema and artifact contract."""

import pytest
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from lfx.base.tools.policy_tool import PolicyCheckedTool


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_guarded_tool_preserves_arguments_config_and_artifacts(asynchronous):
    checks = []

    async def validate():
        checks.append("checked")

    def execute(value: str, config: RunnableConfig):
        assert checks == ["checked"]
        assert config["configurable"]["marker"] == "expected"
        return "displayed", {"value": value}

    async def aexecute(value: str, config: RunnableConfig):
        return execute(value, config)

    original = StructuredTool.from_function(
        func=execute,
        coroutine=aexecute if asynchronous else None,
        name="external",
        description="Return a structured artifact",
        response_format="content_and_artifact",
        return_direct=True,
    )
    guarded = PolicyCheckedTool(original, validate)
    assert guarded.args == original.args
    assert guarded.return_direct is True
    call = {"type": "tool_call", "name": "external", "id": "call-1", "args": {"value": "kept"}}
    config = {"configurable": {"marker": "expected"}}
    result = await guarded.ainvoke(call, config=config) if asynchronous else guarded.invoke(call, config=config)
    assert result.content == "displayed"
    assert result.artifact == {"value": "kept"}
    assert result.tool_call_id == "call-1"
