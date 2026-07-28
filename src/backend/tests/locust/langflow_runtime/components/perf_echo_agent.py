"""Source hook that gives a real Agent a deterministic echo model."""

from typing import Any as _PerfAny

from langchain_core.language_models.chat_models import BaseChatModel as _PerfBaseChatModel
from langchain_core.messages import AIMessage as _PerfAIMessage
from langchain_core.messages import HumanMessage as _PerfHumanMessage
from langchain_core.outputs import ChatGeneration as _PerfChatGeneration
from langchain_core.outputs import ChatResult as _PerfChatResult
from pydantic import PrivateAttr as _PerfPrivateAttr

PERF_FORCE_FIRST_TOOL_CALL = False  # __PERF_FORCE_FIRST_TOOL_CALL__


class _PerfEchoChatModel(_PerfBaseChatModel):
    """Tool-aware model that calls memory once, then echoes the latest user input."""

    _perf_tools: list[_PerfAny] = _PerfPrivateAttr(default_factory=list)
    _perf_called_tool: bool = _PerfPrivateAttr(default=False)

    @property
    def _llm_type(self) -> str:
        return "perf-echo-chat-model"

    def bind_tools(self, tools, **_kwargs):
        self._perf_tools = list(tools)
        return self

    @staticmethod
    def _latest_user_input(messages) -> str:
        for message in reversed(messages):
            if not isinstance(message, _PerfHumanMessage):
                continue
            content = message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for block in content:
                    text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
                    if text:
                        parts.append(str(text))
                return "".join(parts)
            return str(content)
        return ""

    def _result(self, messages) -> _PerfChatResult:
        if PERF_FORCE_FIRST_TOOL_CALL and not self._perf_called_tool and self._perf_tools:
            self._perf_called_tool = True
            tool = self._perf_tools[0]
            name = getattr(tool, "name", None) or "memory_base"
            message = _PerfAIMessage(
                content="",
                tool_calls=[
                    {
                        "name": str(name),
                        "args": {"search_query": "What did I say earlier?"},
                        "id": "perf-memory-tool-call",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            user_input = self._latest_user_input(messages)
            message = _PerfAIMessage(content=user_input)
        return _PerfChatResult(generations=[_PerfChatGeneration(message=message)])

    def _generate(self, messages, stop=None, run_manager=None, **_kwargs):  # noqa: ARG002
        return self._result(messages)

    async def _agenerate(self, messages, stop=None, run_manager=None, **_kwargs):  # noqa: ARG002
        return self._result(messages)


def _perf_model():
    return _PerfEchoChatModel()
