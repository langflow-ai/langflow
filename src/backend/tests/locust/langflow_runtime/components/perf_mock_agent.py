"""Source hook that replaces only an Agent component's external LLM edge."""

from typing import Any as _PerfAny

from langchain_core.language_models.chat_models import BaseChatModel as _PerfBaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel as _PerfFakeListChatModel
from langchain_core.messages import AIMessage as _PerfAIMessage
from langchain_core.outputs import ChatGeneration as _PerfChatGeneration
from langchain_core.outputs import ChatResult as _PerfChatResult
from pydantic import PrivateAttr as _PerfPrivateAttr

PERF_MOCK_LLM_MARKER = "PERF_MOCK_LLM"
PERF_FORCE_FIRST_TOOL_CALL = False  # __PERF_FORCE_FIRST_TOOL_CALL__


class _PerfNoToolChatModel(_PerfFakeListChatModel):
    """Streaming fake model that accepts tools but deliberately calls none."""

    def bind_tools(self, _tools, **_kwargs):
        return self


class _PerfToolAwareChatModel(_PerfBaseChatModel):
    """Deterministic tool-aware model with no provider/network dependency."""

    _perf_tools: list[_PerfAny] = _PerfPrivateAttr(default_factory=list)
    _perf_called_tool: bool = _PerfPrivateAttr(default=False)

    @property
    def _llm_type(self) -> str:
        return "perf-tool-aware-chat-model"

    def bind_tools(self, tools, **_kwargs):
        self._perf_tools = list(tools)
        return self

    def _result(self) -> _PerfChatResult:
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
            message = _PerfAIMessage(content=PERF_MOCK_LLM_MARKER)
        return _PerfChatResult(generations=[_PerfChatGeneration(message=message)])

    def _generate(self, _messages, stop=None, run_manager=None, **_kwargs):  # noqa: ARG002
        return self._result()

    async def _agenerate(self, _messages, stop=None, run_manager=None, **_kwargs):  # noqa: ARG002
        return self._result()


def _perf_model():
    if PERF_FORCE_FIRST_TOOL_CALL:
        return _PerfToolAwareChatModel()
    return _PerfNoToolChatModel(responses=[PERF_MOCK_LLM_MARKER])
