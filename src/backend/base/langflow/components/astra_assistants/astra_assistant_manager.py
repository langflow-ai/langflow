import asyncio

from astra_assistants.astra_assistants_manager import AssistantManager
from loguru import logger

from langflow.base.astra_assistants.util import (
    get_patched_openai_client,
    litellm_model_names,
    tool_names,
    tools_and_names,
)
from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.inputs import DropdownInput, MultilineInput, StrInput
from langflow.graph.graph.state_model import camel_to_snake
from langflow.inputs import DropdownInput, MultilineInput, MultiselectInput, StrInput
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
        MultiselectInput(
            display_name="Tools",
            name="tool_names",
            options=tool_names,
            value=[],
            info="The tools the agent has access to.",
            required=False,
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

    def save_action(self):
        print("puppies")
        if self._vertex:
            input_values = self._vertex.params
            tool_names = input_values.get("tool_names")
            print("got tool names")

            new_outputs = []
            if tool_names is not None:
                for tool_name in tool_names:
                    if tool_name is not None and tool_name != "":
                        tool_name_snake = camel_to_snake(tool_name)
                        # Check if there's an output with a name matching the tool_name
                        if not any(output.name == f"{tool_name_snake}_response" for output in self.outputs):
                            # If no matching output is found, add a new output
                            new_output = Output(
                                display_name=f"{tool_name} Output",
                                name=f"{tool_name_snake}_response",
                                method=f"get_{tool_name_snake}_response",
                            )
                            new_outputs.append(new_output)

                            # Dynamically add a method to get this tool's output
                            async def get_tool_output_method():
                                await self.initialize()
                                return self.tool_output

                            setattr(self, f"get_{tool_name_snake}_response", get_tool_output_method)
                            print(f"set {tool_name_snake}_response")

                    # print(tool_name)
                    # outgoing_edges = [edge for edge in self._vertex.edges if edge.source_id == self._vertex.id]
                    # print(self._vertex.id)
                    # print(self._vertex.edges)
                    # print(outgoing_edges)
                    # for edge in outgoing_edges:
                    #    vertex_id =edge.target_id
                    #    target_v = self._vertex.graph.get_vertex(vertex_id)
                    #    print(target_v.base_name)

            return self, new_outputs
        return None

    async def process_inputs(self):
        print(f"env_set is {self.env_set}")
        print(self.tool_names)
        tools = []
        tool_obj = None
        if self.tool_names is not None and len(self.tool_names) > 0:
            for tool in self.tool_names:
                if tool is not None and tool != "":
                    tool_cls = tools_and_names[tool]
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
