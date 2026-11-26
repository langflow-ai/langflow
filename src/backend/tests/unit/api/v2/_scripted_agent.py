"""A real Agent that asks before each tool call, with a scripted model and tool.

The module is the component's code, so everything it needs is defined here.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from lfx.components.models_and_agents.agent import AgentComponent


class ScriptedModel(BaseChatModel):
    """Calls ``record`` once, then answers with what the tool returned."""

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        results = [m for m in messages if isinstance(m, ToolMessage)]
        if results:
            message = AIMessage(content=f"done:{results[-1].content}")
        else:
            call = {"name": "record", "args": {"value": "effect"}, "id": "call-1", "type": "tool_call"}
            message = AIMessage(content="", tool_calls=[call])
        return ChatResult(generations=[ChatGeneration(message=message)])


class ScriptedAgent(AgentComponent):
    """A real Agent that asks before each tool call, with a scripted model and tool."""

    display_name = "Scripted Agent"
    name = "ScriptedAgent"

    def _get_llm(self):
        return ScriptedModel()

    async def get_agent_requirements(self):
        @tool
        def record(value: str) -> str:
            """Record a value."""
            return value

        record.metadata = {}
        return ScriptedModel(), [], [record]
