"""Compatibility definitions for the ALTK integration retired in Langflow 1.13.0.

Keep the historical import paths available so saved component source can be
inspected and updated without installing the retired SDK. Execution must never
silently bypass ALTK's former validation or invoke a model.
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage

from lfx.base.agents.utils import data_to_messages
from lfx.components.models_and_agents import AgentComponent
from lfx.schema.data import Data
from lfx.schema.message import Message

ALTK_RETIREMENT_MESSAGE = (
    "The ALTK integration was retired in Langflow 1.13.0. Replace this node with "
    "the Agent component and review its tools and validation requirements before "
    "running the flow. Existing ALTK configuration is preserved for reference."
)


class ALTKRetiredError(RuntimeError):
    """An existing flow tried to execute the retired ALTK integration."""

    def __init__(self):
        """Expose replacement guidance for an attempted retired ALTK operation."""
        super().__init__(ALTK_RETIREMENT_MESSAGE)


def normalize_message_content(message: BaseMessage) -> str:
    """Keep the pure content helper used by historical saved component source."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and "text" in item:
                return item["text"]
        return ""
    return str(content)


class BaseToolWrapper:
    """Import-compatible marker for retired ALTK wrappers."""

    def __init__(self, *_args, **_kwargs):
        """Reject construction of a retired ALTK tool wrapper."""
        raise ALTKRetiredError


class ALTKBaseTool(BaseToolWrapper):
    """Import-compatible marker for retired ALTK tools."""


class ToolPipelineManager:
    """Allow saved component construction while rejecting pipeline execution."""

    def __init__(self):
        """Keep the saved pipeline holder constructible without loading the retired SDK."""
        self.wrappers = []

    def configure_wrappers(self, wrappers):  # noqa: ARG002 - preserve saved-source keyword compatibility
        """Reject configuration of retired ALTK wrappers."""
        raise ALTKRetiredError

    def process_tools(self, tools, **_kwargs):  # noqa: ARG002 - preserve saved-source keyword compatibility
        """Reject tool processing through the retired ALTK pipeline."""
        raise ALTKRetiredError


class ALTKBaseAgentComponent(AgentComponent):
    """Preserve saved-node configuration and report retirement before execution."""

    def __init__(self, **kwargs):
        """Initialize the component and its tool-pipeline manager."""
        super().__init__(**kwargs)
        self.pipeline_manager = ToolPipelineManager()

    async def message_response(self) -> Message:
        """Reject execution of a saved ALTK message output."""
        raise ALTKRetiredError

    async def json_response(self) -> Data:
        """Reject execution of a saved ALTK JSON output."""
        raise ALTKRetiredError

    def create_agent_runnable(self, **_kwargs):
        """Reject creation of a runnable for the retired integration."""
        raise ALTKRetiredError

    async def run_agent(self, agent) -> Message:  # noqa: ARG002 - preserve the parent interface
        """Reject agent execution and retain the saved configuration for replacement."""
        raise ALTKRetiredError

    def configure_tool_pipeline(self) -> None:
        """Reject runtime pipeline configuration for a retired node."""
        raise ALTKRetiredError

    def _initialize_tool_pipeline(self) -> None:
        """Reject initialization of the retired tool pipeline."""
        raise ALTKRetiredError

    def update_runnable_instance(self, agent, runnable, tools):  # noqa: ARG002 - legacy interface
        """Reject updates to a retired agent runnable."""
        raise ALTKRetiredError

    def build_conversation_context(self) -> list[BaseMessage]:
        """Preserve the pure history helper referenced by saved component source."""
        context: list[BaseMessage] = []
        if hasattr(self, "chat_history") and self.chat_history:
            if isinstance(self.chat_history, Data):
                context.append(self.chat_history.to_lc_message())
            elif isinstance(self.chat_history, list):
                if all(isinstance(message, Message) for message in self.chat_history):
                    context.extend(message.to_lc_message() for message in self.chat_history)
                else:
                    try:
                        context.extend(data_to_messages(self.chat_history))
                    except (AttributeError, TypeError) as exc:
                        error_message = f"Invalid chat_history list contents: {exc}"
                        raise ValueError(error_message) from exc
            else:
                type_name = type(self.chat_history).__name__
                error_message = (
                    f"chat_history must be a Data object, list of Data/Message objects, or None. Got: {type_name}"
                )
                raise ValueError(error_message)
        if hasattr(self, "input_value") and self.input_value:
            if isinstance(self.input_value, Message):
                context.append(self.input_value.to_lc_message())
            else:
                context.append(HumanMessage(content=str(self.input_value)))
        return context

    def get_user_query(self) -> str:
        """Extract text from message inputs or stringify other query values."""
        if hasattr(self.input_value, "get_text") and callable(self.input_value.get_text):
            return self.input_value.get_text()
        return str(self.input_value)
