import asyncio
from typing import TYPE_CHECKING, cast

from astra_assistants.astra_assistants_manager import AssistantManager
from langchain_core.agents import AgentFinish
from loguru import logger

from langflow.base.agents.events import ExceptionWithMessageError, process_agent_events
from langflow.base.astra_assistants.util import (
    get_patched_openai_client,
    litellm_model_names,
    wrap_base_tool_as_tool_interface,
)
from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.inputs import DropdownInput, HandleInput, MultilineInput, StrInput
from langflow.memory import delete_message
from langflow.schema.content_block import ContentBlock
from langflow.schema.message import Message
from langflow.template import Output
from langflow.utils.constants import MESSAGE_SENDER_AI

if TYPE_CHECKING:
    from langflow.schema.log import SendMessageFunctionType


class AstraAssistantManager(ComponentWithCache):
    display_name = "Astra Assistant Agent"
    description = "Manages Assistant Interactions"
    icon = "AstraDB"

    inputs = [
        DropdownInput(
            name="model_name",
            display_name="Model",
            advanced=False,
            options=litellm_model_names,
            value="gpt-4o-mini",
        ),
        StrInput(
            name="instructions",
            display_name="Agent Instructions",
            info="Instructions for the assistant, think of these as the system prompt.",
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            required=False,
            info="These are the tools that the agent can use to help with tasks.",
        ),
        # DropdownInput(
        #    display_name="Tools",
        #    name="tool",
        #    options=tool_names,
        # ),
        MultilineInput(
            name="user_message",
            display_name="User Message",
            info="User message to pass to the run.",
        ),
        MultilineInput(
            name="input_thread_id",
            display_name="Thread ID (optional)",
            info="ID of the thread",
        ),
        MultilineInput(
            name="input_assistant_id",
            display_name="Assistant ID (optional)",
            info="ID of the assistant",
        ),
        MultilineInput(
            name="env_set",
            display_name="Environment Set",
            info="Dummy input to allow chaining with Dotenv Component.",
        ),
    ]

    outputs = [
        Output(display_name="Assistant Response", name="assistant_response", method="get_assistant_response"),
        Output(display_name="Tool output", name="tool_output", method="get_tool_output"),
        Output(display_name="Thread Id", name="output_thread_id", method="get_thread_id"),
        Output(display_name="Assistant Id", name="output_assistant_id", method="get_assistant_id"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.lock = asyncio.Lock()
        self.initialized: bool = False
        self._assistant_response: Message = None  # type: ignore[assignment]
        self._tool_output: Message = None  # type: ignore[assignment]
        self._thread_id: Message = None  # type: ignore[assignment]
        self._assistant_id: Message = None  # type: ignore[assignment]
        self.client = get_patched_openai_client(self._shared_component_cache)

    async def get_assistant_response(self) -> Message:
        await self.initialize()
        self.status = self._assistant_response
        return self._assistant_response

    async def get_tool_output(self) -> Message:
        await self.initialize()
        self.status = self._tool_output
        return self._tool_output

    async def get_thread_id(self) -> Message:
        await self.initialize()
        self.status = self._thread_id
        return self._thread_id

    async def get_assistant_id(self) -> Message:
        await self.initialize()
        self.status = self._assistant_id
        return self._assistant_id

    async def initialize(self) -> None:
        async with self.lock:
            if not self.initialized:
                await self.process_inputs()
                self.initialized = True

    async def process_inputs(self) -> None:
        logger.info(f"env_set is {self.env_set}")
        logger.info(self.tools)
        tools = []
        tool_obj = None
        for tool in self.tools:
            tool_obj = wrap_base_tool_as_tool_interface(tool)
            tools.append(tool_obj)

        assistant_id = None
        thread_id = None
        if self.input_assistant_id:
            assistant_id = self.input_assistant_id
        if self.input_thread_id:
            thread_id = self.input_thread_id

        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name=self.display_name or "Astra Assistant",
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Assistant Steps", contents=[])],
            session_id=session_id,
        )

        assistant_manager = AssistantManager(
            instructions=self.instructions,
            model=self.model_name,
            name="managed_assistant",
            tools=tools,
            client=self.client,
            thread_id=thread_id,
            assistant_id=assistant_id,
        )

        async def step_iterator():
            # Initial event
            yield {"event": "on_chain_start", "name": "AstraAssistant", "data": {"input": {"text": self.user_message}}}

            content = self.user_message
            result = await assistant_manager.run_thread(content=content, tool=tool_obj)

            # Tool usage if present
            if "output" in result:
                yield {"event": "on_tool_start", "name": "tool", "data": {"input": {"text": self.user_message}}}
                yield {"event": "on_tool_end", "name": "tool", "data": {"output": result["output"]}}

            self._assistant_response = Message(text=result["text"])
            if "decision" in result:
                self._tool_output = Message(text=str(result["decision"].is_complete))
            else:
                self._tool_output = Message(text=result["text"])
            self._thread_id = Message(text=assistant_manager.thread.id)
            self._assistant_id = Message(text=assistant_manager.assistant.id)

            # Final event - format it like AgentFinish to match the expected format
            yield {
                "event": "on_chain_end",
                "name": "AstraAssistant",
                "data": {"output": AgentFinish(return_values={"output": result["text"]}, log="")},
            }

        try:
            if hasattr(self, "send_message"):
                processed_result = await process_agent_events(
                    step_iterator(),
                    agent_message,
                    cast("SendMessageFunctionType", self.send_message),
                )
                self.status = processed_result
        except ExceptionWithMessageError as e:
            msg_id = e.agent_message.id
            await delete_message(id_=msg_id)
            await self._send_message_event(e.agent_message, category="remove_message")
            raise
        except Exception:
            raise
