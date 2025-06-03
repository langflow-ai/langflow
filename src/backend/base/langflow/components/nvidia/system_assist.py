import asyncio

from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.io import MessageTextInput, Output
from langflow.schema import Message
from langflow.services.cache.utils import CacheMiss

RISE_INITIALIZED_KEY = "rise_initialized"


class NvidiaSystemAssistComponent(ComponentWithCache):
    display_name = "NVIDIA System-Assist"
    description = (
        "(Windows only) Prompts NVIDIA System-Assist to interact with the NVIDIA GPU Driver. "
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
            info="Enter a prompt for NVIDIA System-Assist to process. Example: 'What is my GPU?'",
            value="",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="sys_assist_prompt"),
    ]

    def maybe_register_rise_client(self):
        try:
            from gassist.rise import register_rise_client

            rise_initialized = self._shared_component_cache.get(RISE_INITIALIZED_KEY)
            if not isinstance(rise_initialized, CacheMiss) and rise_initialized:
                return
            self.log("Initializing Rise Client")

            register_rise_client()
            self._shared_component_cache.set(key=RISE_INITIALIZED_KEY, value=True)
        except ImportError as e:
            msg = "NVIDIA System-Assist is Windows only and not supported on this platform"
            raise ValueError(msg) from e
        except Exception as e:
            msg = f"An error occurred initializing NVIDIA System-Assist: {e}"
            raise ValueError(msg) from e

    async def sys_assist_prompt(self) -> Message:
        try:
            from gassist.rise import send_rise_command
        except ImportError as e:
            msg = "NVIDIA System-Assist is Windows only and not supported on this platform"
            raise ValueError(msg) from e

        self.maybe_register_rise_client()

        response = await asyncio.to_thread(send_rise_command, self.prompt)

        return Message(text=response["completed_response"]) if response is not None else Message(text=None)
