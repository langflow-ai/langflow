import asyncio
from asyncio import to_thread
from typing import TYPE_CHECKING, Any, cast

from astra_assistants.astra_assistants_manager import AssistantManager
from langchain_core.agents import AgentFinish
from loguru import logger

from lfx.base.agents.events import ExceptionWithMessageError, process_agent_events
from lfx.base.astra_assistants.util import (
    get_patched_openai_client,
    litellm_model_names,
    sync_upload,
    wrap_base_tool_as_tool_interface,
)
from lfx.custom.custom_component.component_with_cache import ComponentWithCache
from lfx.inputs.inputs import DropdownInput, FileInput, HandleInput, MultilineInput
from lfx.memory import delete_message
from lfx.schema.content_block import ContentBlock
from lfx.schema.message import Message
from lfx.template.field.base import Output
from lfx.utils.constants import MESSAGE_SENDER_AI

if TYPE_CHECKING:
    from lfx.schema.log import SendMessageFunctionType


class AstraAssistantManager(ComponentWithCache):
    display_name = "Astra Assistant Agent"
    name = "Astra Assistant Agent"
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
        MultilineInput(
            name="instructions",
            display_name="Agent Instructions",
            info="Instructions for the assistant, think of these as the system prompt.",
        ),
        HandleInput(
            name="input_tools",
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
            name="user_message", display_name="User Message", info="User message to pass to the run.", tool_mode=True
        ),
        FileInput(
            name="file",
            display_name="File(s) for retrieval",
            list=True,
            info="Files to be sent with the message.",
            required=False,
            show=True,
            file_types=[
                "txt",
                "md",
                "mdx",
                "csv",
                "json",
                "yaml",
                "yml",
                "xml",
                "html",
                "htm",
                "pdf",
                "docx",
                "py",
                "sh",
                "sql",
                "js",
                "ts",
                "tsx",
                "jpg",
                "jpeg",
                "png",
                "bmp",
                "image",
                "zip",
                "tar",
                "tgz",
                "bz2",
                "gz",
                "c",
                "cpp",
                "cs",
                "css",
                "go",
                "java",
                "php",
                "rb",
                "tex",
                "doc",
                "docx",
                "ppt",
                "pptx",
                "xls",
                "xlsx",
                "jsonl",
            ],
        ),
        MultilineInput(
            name="input_thread_id",
            display_name="Thread ID (optional)",
            info="ID of the thread",
            advanced=True,
        ),
        MultilineInput(
            name="input_assistant_id",
            display_name="Assistant ID (optional)",
            info="ID of the assistant",
            advanced=True,
        ),
        MultilineInput(
            name="env_set",
            display_name="Environment Set",
            info="Dummy input to allow chaining with Dotenv Component.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Assistant Response", name="assistant_response", method="get_assistant_response"),
        Output(display_name="Tool output", name="tool_output", method="get_tool_output", hidden=True),
        Output(display_name="Thread Id", name="output_thread_id", method="get_thread_id", hidden=True),
        Output(display_name="Assistant Id", name="output_assistant_id", method="get_assistant_id", hidden=True),
        Output(display_name="Vector Store Id", name="output_vs_id", method="get_vs_id", hidden=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.lock = asyncio.Lock()
        self.initialized: bool = False
        self._assistant_response: Message = None  # type: ignore[assignment]
        self._tool_output: Message = None  # type: ignore[assignment]
        self._thread_id: Message = None  # type: ignore[assignment]
        self._assistant_id: Message = None  # type: ignore[assignment]
        self._vs_id: Message = None  # type: ignore[assignment]
        self.client = get_patched_openai_client(self._shared_component_cache)
        self.input_tools: list[Any]

    async def get_assistant_response(self) -> Message:
        await self.initialize()
        self.status = self._assistant_response
        return self._assistant_response

    async def get_vs_id(self) -> Message:
        await self.initialize()
        self.status = self._vs_id
        return self._vs_id

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
        logger.info(self.input_tools)
        tools = []
        tool_obj = None
        if self.input_tools is None:
            self.input_tools = []
        for tool in self.input_tools:
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

        if self.file:
            file = await to_thread(sync_upload, self.file, assistant_manager.client)
            vector_store = assistant_manager.client.beta.vector_stores.create(name="my_vs", file_ids=[file.id])
            assistant_tools = assistant_manager.assistant.tools
            assistant_tools += [{"type": "file_search"}]
            assistant = assistant_manager.client.beta.assistants.update(
                assistant_manager.assistant.id,
                tools=assistant_tools,
                tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
            )
            assistant_manager.assistant = assistant

        async def step_iterator():
            # Initial event
            yield {"event": "on_chain_start", "name": "AstraAssistant", "data": {"input": {"text": self.user_message}}}

            content = self.user_message
            result = await assistant_manager.run_thread(content=content, tool=tool_obj)

            # Tool usage if present
            if "output" in result and "arguments" in result:
                yield {"event": "on_tool_start", "name": "tool", "data": {"input": {"text": str(result["arguments"])}}}
                yield {"event": "on_tool_end", "name": "tool", "data": {"output": result["output"]}}

            if "file_search" in result and result["file_search"] is not None:
                yield {"event": "on_tool_start", "name": "tool", "data": {"input": {"text": self.user_message}}}
                file_search_str = ""
                for chunk in result["file_search"].to_dict().get("chunks", []):
                    file_search_str += f"## Chunk ID: `{chunk['chunk_id']}`\n"
                    file_search_str += f"**Content:**\n\n```\n{chunk['content']}\n```\n\n"
                    if "score" in chunk:
                        file_search_str += f"**Score:** {chunk['score']}\n\n"
                    if "file_id" in chunk:
                        file_search_str += f"**File ID:** `{chunk['file_id']}`\n\n"
                    if "file_name" in chunk:
                        file_search_str += f"**File Name:** `{chunk['file_name']}`\n\n"
                    if "bytes" in chunk:
                        file_search_str += f"**Bytes:** {chunk['bytes']}\n\n"
                    if "search_string" in chunk:
                        file_search_str += f"**Search String:** {chunk['search_string']}\n\n"
                yield {"event": "on_tool_end", "name": "tool", "data": {"output": file_search_str}}

            if "text" not in result:
                msg = f"No text in result, {result}"
                raise ValueError(msg)

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
