from openai.types.beta.threads.run_submit_tool_outputs_params import ToolOutput

from langflow.components.astra_assistants.tools.flowgen import FlowgenTool
from langflow.custom import Component
from langflow.inputs import DropdownInput, StrInput, MultilineInput
from langflow.schema.message import Message
from langflow.template import Output
from astra_assistants.astra_assistants_manager import AssistantManager


class AstraAssistantManager(Component):
    display_name = "Astra Assistant Manager"
    description = "Manages Assistant Interactions"
    icon = "bot"

    # take inputs from this init def
    # def __init__(self, instructions: str, model: str = "gpt-4o", name: str = "managed_assistant", tools: List[ToolInterface] = None, thread_id: str = None, thread: str = None, assistant_id: str = None):
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
            options=["gpt-4o-mini"],
            value="gpt-4o-mini",
        ),
        DropdownInput(
            display_name="Tools",
            name="tools",
            options=["flowgen"],
            value="flowgen",
        ),
        MultilineInput(
            name="user_message",
            display_name="User Message",
            info="User message to pass to the run.",
        ),
        StrInput(
            name="thread_id",
            display_name="Thread ID",
            info="ID of the thread optional",
        ),
        StrInput(
            name="assistant_id",
            display_name="Assistant ID (optional)",
            info="Thread",
        ),
        MultilineInput(
            name="env_set",
            display_name="Environment Set",
            info="Dummy input to allow chaining with Dotenv Component.",
        ),
    ]

    outputs = [Output(display_name="Assistant Response", name="assistant_response", method="process_inputs")]


    async def process_inputs(self) -> Message:
        print(f"env_set is {self.env_set}")
        flowgen_tool = FlowgenTool()
        #TODO: make tools dynamic
        tools = [flowgen_tool]
        #TODO: maybe pass thread_id and assistant_id
        assistant_manager = AssistantManager(instructions=self.instructions, model=self.model_name, name="managed_assistant", tools=tools)

        content=self.user_message
        result: ToolOutput = await assistant_manager.run_thread(
            content=content,
            tool=flowgen_tool
        )
        message = Message(text=result)
        return message
