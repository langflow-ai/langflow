"""Reusable base classes for ALTK agent components and tool wrappers.

This module abstracts common orchestration so concrete components can focus
on user-facing configuration and small customizations.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, cast

from altk.core.llm import get_llm
from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain_anthropic.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableBinding
from langchain_core.tools import BaseTool
from langchain_openai.chat_models.base import ChatOpenAI
from pydantic import Field

from lfx.base.agents.callback import AgentAsyncHandler
from lfx.base.agents.events import ExceptionWithMessageError, process_agent_events
from lfx.base.agents.utils import data_to_messages, get_chat_output_sender_name
from lfx.components.agents import AgentComponent
from lfx.log.logger import logger
from lfx.memory import delete_message
from lfx.schema.content_block import ContentBlock
from lfx.schema.data import Data

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lfx.schema.log import SendMessageFunctionType

from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI


def normalize_message_content(message: BaseMessage) -> str:
    """Normalize message content to handle inconsistent formats from Data.to_lc_message().

    Args:
        message: A BaseMessage that may have content as either:
                - str (for AI messages)
                - list[dict] (for User messages in format [{"type": "text", "text": "..."}])

    Returns:
        str: The extracted text content

    Note:
        This addresses the inconsistency in lfx.schema.data.Data.to_lc_message() where:
        - User messages: content = [{"type": "text", "text": text}] (list format)
        - AI messages: content = text (string format)
    """
    content = message.content

    # Handle string format (AI messages)
    if isinstance(content, str):
        return content

    # Handle list format (User messages)
    if isinstance(content, list) and len(content) > 0:
        # Extract text from first content block that has 'text' field
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and "text" in item:
                return item["text"]
        # If no text found, return empty string (e.g., image-only messages)
        return ""

    # Handle empty list or other formats
    if isinstance(content, list):
        return ""

    # Fallback for any other format
    return str(content)


# === Base Tool Wrapper Architecture ===


class BaseToolWrapper(ABC):
    """Base class for all tool wrappers in the pipeline.

    Tool wrappers can enhance tools by adding pre-execution validation,
    post-execution processing, or other capabilities.
    """

    @abstractmethod
    def wrap_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
        """Wrap a tool with enhanced functionality."""

    def initialize(self, **_kwargs) -> bool:  # pragma: no cover - trivial
        """Initialize any resources needed by the wrapper."""
        return True

    @property
    def is_available(self) -> bool:  # pragma: no cover - trivial
        """Check if the wrapper is available for use."""
        return True


class ALTKBaseTool(BaseTool):
    """Base class for tools that need agent interaction and ALTK LLM access.

    Provides common functionality for tool execution and ALTK LLM object creation.
    """

    name: str = Field(...)
    description: str = Field(...)
    wrapped_tool: BaseTool = Field(...)
    agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor = Field(...)

    def _run(self, *args, **kwargs) -> str:
        """Abstract method implementation that uses the wrapped tool execution."""
        return self._execute_tool(*args, **kwargs)

    def _execute_tool(self, *args, **kwargs) -> str:
        """Execute the wrapped tool with compatibility across LC versions."""
        # BaseTool.run() expects tool_input as first argument
        if args:
            # Use first arg as tool_input, pass remaining args
            tool_input = args[0]
            return self.wrapped_tool.run(tool_input, *args[1:])
        if kwargs:
            # Use kwargs dict as tool_input
            return self.wrapped_tool.run(kwargs)
        # No arguments - pass empty dict as tool_input
        return self.wrapped_tool.run({})

    def _get_altk_llm_object(self, *, use_output_val: bool = True) -> Any:
        """Extract the underlying LLM and map it to an ALTK client object."""
        llm_object: BaseChatModel | None = None
        steps = getattr(self.agent, "steps", None)
        if steps:
            for step in steps:
                if isinstance(step, RunnableBinding) and isinstance(step.bound, BaseChatModel):
                    llm_object = step.bound
                    break

        if isinstance(llm_object, ChatAnthropic):
            model_name = f"anthropic/{llm_object.model}"
            api_key = llm_object.anthropic_api_key.get_secret_value()
            llm_client_type = "litellm.output_val" if use_output_val else "litellm"
            llm_client = get_llm(llm_client_type)
            llm_client_obj = llm_client(model_name=model_name, api_key=api_key)
        elif isinstance(llm_object, ChatOpenAI):
            model_name = llm_object.model_name
            api_key = llm_object.openai_api_key.get_secret_value()
            llm_client_type = "openai.sync.output_val" if use_output_val else "openai.sync"
            llm_client = get_llm(llm_client_type)
            llm_client_obj = llm_client(model=model_name, api_key=api_key)
        else:
            logger.info("ALTK currently only supports OpenAI and Anthropic models through Langflow.")
            llm_client_obj = None

        return llm_client_obj


class ToolPipelineManager:
    """Manages a sequence of tool wrappers and applies them to tools."""

    def __init__(self):
        self.wrappers: list[BaseToolWrapper] = []

    def clear(self) -> None:
        self.wrappers.clear()

    def add_wrapper(self, wrapper: BaseToolWrapper) -> None:
        self.wrappers.append(wrapper)

    def configure_wrappers(self, wrappers: list[BaseToolWrapper]) -> None:
        """Replace current wrappers with new configuration."""
        self.clear()
        for wrapper in wrappers:
            self.add_wrapper(wrapper)

    def process_tools(self, tools: list[BaseTool], **kwargs) -> list[BaseTool]:
        return [self._apply_wrappers_to_tool(tool, **kwargs) for tool in tools]

    def _apply_wrappers_to_tool(self, tool: BaseTool, **kwargs) -> BaseTool:
        wrapped_tool = tool
        for wrapper in reversed(self.wrappers):
            if wrapper.is_available:
                wrapped_tool = wrapper.wrap_tool(wrapped_tool, **kwargs)
        return wrapped_tool


# === Base Agent Component Orchestration ===


class ALTKBaseAgentComponent(AgentComponent):
    """Base agent component that centralizes orchestration and hooks.

    Subclasses should override `get_tool_wrappers` to provide their wrappers
    and can customize context building if needed.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pipeline_manager = ToolPipelineManager()

    # ---- Hooks for subclasses ----
    def configure_tool_pipeline(self) -> None:
        """Configure the tool pipeline with wrappers. Subclasses override this."""
        # Default: no wrappers
        self.pipeline_manager.clear()

    def build_conversation_context(self) -> list[BaseMessage]:
        """Create conversation context from input and chat history."""
        context: list[BaseMessage] = []

        # Add chat history to maintain chronological order
        if hasattr(self, "chat_history") and self.chat_history:
            if isinstance(self.chat_history, Data):
                context.append(self.chat_history.to_lc_message())
            elif isinstance(self.chat_history, list):
                if all(isinstance(m, Message) for m in self.chat_history):
                    context.extend([m.to_lc_message() for m in self.chat_history])
                else:
                    # Assume list of Data objects, let data_to_messages handle validation
                    try:
                        context.extend(data_to_messages(self.chat_history))
                    except (AttributeError, TypeError) as e:
                        error_message = f"Invalid chat_history list contents: {e}"
                        raise ValueError(error_message) from e
            else:
                # Reject all other types (strings, numbers, etc.)
                type_name = type(self.chat_history).__name__
                error_message = (
                    f"chat_history must be a Data object, list of Data/Message objects, or None. Got: {type_name}"
                )
                raise ValueError(error_message)

        # Then add current input to maintain chronological order
        if hasattr(self, "input_value") and self.input_value:
            if isinstance(self.input_value, Message):
                context.append(self.input_value.to_lc_message())
            else:
                context.append(HumanMessage(content=str(self.input_value)))

        return context

    def get_user_query(self) -> str:
        if hasattr(self.input_value, "get_text") and callable(self.input_value.get_text):
            return self.input_value.get_text()
        return str(self.input_value)

    # ---- Internal helpers reused by run/update ----
    def _initialize_tool_pipeline(self) -> None:
        """Initialize the tool pipeline by calling the subclass configuration."""
        self.configure_tool_pipeline()

    def update_runnable_instance(
        self, agent: AgentExecutor, runnable: AgentExecutor, tools: Sequence[BaseTool]
    ) -> AgentExecutor:
        """Update the runnable instance with processed tools.

        Subclasses can override this method to customize tool processing.
        The default implementation applies the tool wrapper pipeline.
        """
        user_query = self.get_user_query()
        conversation_context = self.build_conversation_context()

        self._initialize_tool_pipeline()
        processed_tools = self.pipeline_manager.process_tools(
            list(tools or []),
            agent=agent,
            user_query=user_query,
            conversation_context=conversation_context,
        )

        runnable.tools = processed_tools
        return runnable

    async def run_agent(
        self,
        agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor,
    ) -> Message:
        if isinstance(agent, AgentExecutor):
            runnable = agent
        else:
            # note the tools are not required to run the agent, hence the validation removed.
            handle_parsing_errors = hasattr(self, "handle_parsing_errors") and self.handle_parsing_errors
            verbose = hasattr(self, "verbose") and self.verbose
            max_iterations = hasattr(self, "max_iterations") and self.max_iterations
            runnable = AgentExecutor.from_agent_and_tools(
                agent=agent,
                tools=self.tools or [],
                handle_parsing_errors=handle_parsing_errors,
                verbose=verbose,
                max_iterations=max_iterations,
            )
        runnable = self.update_runnable_instance(agent, runnable, self.tools)

        # Convert input_value to proper format for agent
        if hasattr(self.input_value, "to_lc_message") and callable(self.input_value.to_lc_message):
            lc_message = self.input_value.to_lc_message()
            input_text = lc_message.content if hasattr(lc_message, "content") else str(lc_message)
        else:
            lc_message = None
            input_text = self.input_value

        input_dict: dict[str, str | list[BaseMessage]] = {}
        if hasattr(self, "system_prompt"):
            input_dict["system_prompt"] = self.system_prompt
        if hasattr(self, "chat_history") and self.chat_history:
            if (
                hasattr(self.chat_history, "to_data")
                and callable(self.chat_history.to_data)
                and self.chat_history.__class__.__name__ == "Data"
            ):
                input_dict["chat_history"] = data_to_messages(self.chat_history)
            # Handle both lfx.schema.message.Message and langflow.schema.message.Message types
            if all(hasattr(m, "to_data") and callable(m.to_data) and "text" in m.data for m in self.chat_history):
                input_dict["chat_history"] = data_to_messages(self.chat_history)
            if all(isinstance(m, Message) for m in self.chat_history):
                input_dict["chat_history"] = data_to_messages([m.to_data() for m in self.chat_history])
        if hasattr(lc_message, "content") and isinstance(lc_message.content, list):
            # ! Because the input has to be a string, we must pass the images in the chat_history

            image_dicts = [item for item in lc_message.content if item.get("type") == "image"]
            lc_message.content = [item for item in lc_message.content if item.get("type") != "image"]

            if "chat_history" not in input_dict:
                input_dict["chat_history"] = []
            if isinstance(input_dict["chat_history"], list):
                input_dict["chat_history"].extend(HumanMessage(content=[image_dict]) for image_dict in image_dicts)
            else:
                input_dict["chat_history"] = [HumanMessage(content=[image_dict]) for image_dict in image_dicts]
        input_dict["input"] = input_text
        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        try:
            sender_name = get_chat_output_sender_name(self)
        except AttributeError:
            sender_name = self.display_name or "AI"

        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name=sender_name,
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=session_id or uuid.uuid4(),
        )
        try:
            result = await process_agent_events(
                runnable.astream_events(
                    input_dict,
                    config={
                        "callbacks": [
                            AgentAsyncHandler(self.log),
                            *self.get_langchain_callbacks(),
                        ]
                    },
                    version="v2",
                ),
                agent_message,
                cast("SendMessageFunctionType", self.send_message),
            )
        except ExceptionWithMessageError as e:
            if hasattr(e, "agent_message") and hasattr(e.agent_message, "id"):
                msg_id = e.agent_message.id
                await delete_message(id_=msg_id)
            await self._send_message_event(e.agent_message, category="remove_message")
            logger.error(f"ExceptionWithMessageError: {e}")
            raise
        except Exception as e:
            # Log or handle any other exceptions
            logger.error(f"Error: {e}")
            raise

        self.status = result
        return result
