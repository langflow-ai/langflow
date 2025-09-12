from datetime import datetime, timezone
from typing import Any

from langchain_core.language_models import BaseLanguageModel, BaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field, field_validator, model_serializer

from lfx.field_typing import LanguageModel
from lfx.schema.data import Data


class AgentContext(BaseModel):
    tools: dict[str, Any]
    llm: Any
    context: str = ""
    iteration: int = 0
    max_iterations: int = 5
    thought: str = ""
    last_action: Any = None
    last_action_result: Any = None
    final_answer: Any = ""
    context_history: list[tuple[str, str, str]] = Field(default_factory=list)

    @model_serializer(mode="plain")
    def serialize_agent_context(self):
        serliazed_llm = self.llm.to_json() if hasattr(self.llm, "to_json") else str(self.llm)
        serliazed_tools = {k: v.to_json() if hasattr(v, "to_json") else str(v) for k, v in self.tools.items()}
        return {
            "tools": serliazed_tools,
            "llm": serliazed_llm,
            "context": self.context,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "thought": self.thought,
            "last_action": self.last_action.to_json()
            if hasattr(self.last_action, "to_json")
            else str(self.last_action),
            "action_result": self.last_action_result.to_json()
            if hasattr(self.last_action_result, "to_json")
            else str(self.last_action_result),
            "final_answer": self.final_answer,
            "context_history": self.context_history,
        }

    @field_validator("llm", mode="before")
    @classmethod
    def validate_llm(cls, v) -> LanguageModel:
        if not isinstance(v, BaseLLM | BaseChatModel | BaseLanguageModel):
            msg = "llm must be an instance of LanguageModel"
            raise TypeError(msg)
        return v

    def to_data_repr(self):
        data_objs = []
        for name, val, time_str in self.context_history:
            content = val.content if hasattr(val, "content") else val
            data_objs.append(Data(name=name, value=content, timestamp=time_str))

        sorted_data_objs = sorted(data_objs, key=lambda x: datetime.fromisoformat(x.timestamp), reverse=True)

        sorted_data_objs.append(
            Data(
                name="Formatted Context",
                value=self.get_full_context(),
            )
        )
        return sorted_data_objs

    def _build_tools_context(self):
        tool_context = ""
        for tool_name, tool_obj in self.tools.items():
            tool_context += f"{tool_name}: {tool_obj.description}\n"
        return tool_context

    def _build_init_context(self):
        return f"""
{self.context}

"""

    def model_post_init(self, _context: Any) -> None:
        if hasattr(self.llm, "bind_tools"):
            self.llm = self.llm.bind_tools(self.tools.values())
        if self.context:
            self.update_context("Initial Context", self.context)

    def update_context(self, key: str, value: str):
        self.context_history.insert(0, (key, value, datetime.now(tz=timezone.utc).astimezone().isoformat()))

    def _serialize_context_history_tuple(self, context_history_tuple: tuple[str, str, str]) -> str:
        name, value, _ = context_history_tuple
        if hasattr(value, "content"):
            value = value.content
        elif hasattr(value, "log"):
            value = value.log
        return f"{name}: {value}"

    def get_full_context(self) -> str:
        context_history_reversed = self.context_history[::-1]
        context_formatted = "\n".join(
            [
                self._serialize_context_history_tuple(context_history_tuple)
                for context_history_tuple in context_history_reversed
            ]
        )
        return f"""
Context:
{context_formatted}
"""
