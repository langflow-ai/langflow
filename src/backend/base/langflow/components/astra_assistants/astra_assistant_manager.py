from openai.types.beta.threads.run_submit_tool_outputs_params import ToolOutput
from langflow.components.astra_assistants.tools.flowgen import FlowgenTool
from langflow.components.astra_assistants.util import get_patched_openai_client, litellm_model_names, tool_names, \
    tools_and_names
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
            options=litellm_model_names,
            #options=["gpt-4o-mini"],
            value="gpt-4o-mini",
        ),
        DropdownInput(
            display_name="Tools",
            name="tools",
            options=tool_names,
            #options=["flowgen"],
        ),
        MultilineInput(
            name="user_message",
            display_name="User Message",
            info="User message to pass to the run.",
        ),
        StrInput(
            name="thread_id",
            display_name="Thread ID (optional)",
            info="ID of the thread",
        ),
        StrInput(
            name="assistant_id",
            display_name="Assistant ID (optional)",
            info="ID of the assistant",
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
        print(self.tools)
        tool_cls = tools_and_names[self.tools]
        tool_obj = tool_cls()
        client = get_patched_openai_client()
        assistant_id = None
        thread_id = None
        if self.assistant_id:
            assistant_id = self.assistant_id
        if self.thread_id:
            thread_id = self.thread_id
        assistant_manager = AssistantManager(instructions=self.instructions, model=self.model_name, name="managed_assistant", tools=[tool_obj], client=client, thread_id=thread_id, assistant_id=assistant_id)

        content=self.user_message
        result: ToolOutput = await assistant_manager.run_thread(
            content=content,
            tool=tool_obj
        )
        message = Message(text=result['text'])
        return message
