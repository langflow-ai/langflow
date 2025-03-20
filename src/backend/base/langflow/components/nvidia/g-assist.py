import asyncio
from langflow.custom import Component
from langflow.io import MessageTextInput, Output

from rise.rise import register_rise_client, send_rise_command


class RiseComponent(Component):
    display_name = "Nvidia G-Assist"
    description = "Executes commands using NVIDIA G-Assist."
    documentation = "https://docs.langflow.org/components-custom-components"
    icon = "code"
    name = "RiseComponent"
    rise_client = None

    inputs = [
        MessageTextInput(
            name="command",
            display_name="Rise Command",
            info="Enter a command to send to the rise library.",
            value="default_command",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="build_output"),
    ]

    async def build_output(self) -> str:
        if self.rise_client is None:
            self.rise_client = register_rise_client()
        # Wrap the blocking send_rise_command call in a thread to avoid blocking the event loop.
        response = await asyncio.to_thread(send_rise_command, self.command)
        return response
