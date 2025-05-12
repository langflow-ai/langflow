import asyncio

from gassist.rise import register_rise_client, send_rise_command

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Message


class NvidiaSystemAssistComponent(Component):
    display_name = "NVIDIA System-Assist"
    description = (
        "Prompts NVIDIA System-Assist to interact with the NVIDIA GPU Driver. "
        "The user may query GPU specifications, state, and ask the NV-API to perform "
        "several GPU-editing acations. The prompt must be human-readable language."
    )
    documentation = "https://docs.langflow.org/components-custom-components"
    icon = "NVIDIA"
    rise_initialized = False

    inputs = [
        MessageTextInput(
            name="prompt",
            display_name="System-Assist Prompt",
            info="Enter a prompt for NVIDIA System-Assist to process.",
            value="",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="sys_assist_prompt"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not NvidiaSystemAssistComponent.rise_initialized:
            register_rise_client()
            NvidiaSystemAssistComponent.rise_initialized = True

    async def sys_assist_prompt(self) -> Message:
        # Wrap the blocking send_rise_command call in a thread to avoid blocking the event loop.
        response = await asyncio.to_thread(send_rise_command, self.prompt)
        if response is not None:
            return Message(text=response["completed_response"])
        return Message(text=None)
