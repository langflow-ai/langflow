import asyncio

from astra_assistants.astra_assistants_manager import AssistantManager

from langflow.components.astra_assistants.util import (
    get_patched_openai_client,
    litellm_model_names,
    tool_names,
    tools_and_names,
)
from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.inputs import DropdownInput, MultilineInput, StrInput
from langflow.schema.message import Message
from langflow.template import Output


class AstraAssistantManager(ComponentWithCache):
    display_name = "Astra Assistant Manager"
    description = "Manages Assistant Interactions"
    icon = "bot"

    inputs = [
        StrInput(
            name="instructions",
            display_name="Instructions",
            info="Instructions for the assistant, think of these as the system prompt.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=litellm_model_names,
            value="gpt-4o-mini",
        ),
        DropdownInput(
            display_name="Tool",
            name="tool",
            options=tool_names,
        ),
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lock = asyncio.Lock()
        self.initialized = False
        self.assistant_response = None
        self.tool_output = None
        self.thread_id = None
        self.assistant_id = None
        self.client = get_patched_openai_client(self._shared_component_cache)

    async def get_assistant_response(self) -> Message:
        await self.initialize()
        return self.assistant_response

    async def get_tool_output(self) -> Message:
        await self.initialize()
        return self.tool_output

    async def get_thread_id(self) -> Message:
        await self.initialize()
        return self.thread_id

    async def get_assistant_id(self) -> Message:
        await self.initialize()
        return self.assistant_id

    async def initialize(self):
        async with self.lock:
            if not self.initialized:
                await self.process_inputs()
                self.initialized = True

    async def process_inputs(self):
        print(f"env_set is {self.env_set}")
        print(self.tool)
        tools = []
        tool_obj = None
        if self.tool is not None and self.tool != "":
            tool_cls = tools_and_names[self.tool]
            tool_obj = tool_cls()
            tools.append(tool_obj)
        assistant_id = None
        thread_id = None
        if self.input_assistant_id:
            assistant_id = self.input_assistant_id
        if self.input_thread_id:
            thread_id = self.input_thread_id
        assistant_manager = AssistantManager(
            instructions=self.instructions,
            model=self.model_name,
            name="managed_assistant",
            tools=tools,
            client=self.client,
            thread_id=thread_id,
            assistant_id=assistant_id,
        )

        content = self.user_message
        result = await assistant_manager.run_thread(content=content, tool=tool_obj)
        self.assistant_response = Message(text=result["text"])
        if "decision" in result:
            self.tool_output = Message(text=str(result["decision"].is_complete))
        else:
            self.tool_output = Message(text=result["text"])
        self.thread_id = Message(text=assistant_manager.thread.id)
        self.assistant_id = Message(text=assistant_manager.assistant.id)
