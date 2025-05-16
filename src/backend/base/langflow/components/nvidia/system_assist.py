import asyncio
import contextlib

from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.io import MessageTextInput, Output
from langflow.schema import Message
from langflow.services.cache.utils import CacheMiss


class NvidiaSystemAssistComponent(ComponentWithCache):
    display_name = "NVIDIA System-Assist"
    description = (
        "Prompts NVIDIA System-Assist to interact with the NVIDIA GPU Driver. "
        "The user may query GPU specifications, state, and ask the NV-API to perform "
        "several GPU-editing acations. The prompt must be human-readable language."
        "(Windows only)"
    )
    documentation = "https://docs.langflow.org/components-custom-components"
    icon = "NVIDIA"
    rise_initialized = False

    def maybe_register_rise_client(self):
        rise_initialized = self._shared_component_cache.get("rise_initialized")
        if not isinstance(rise_initialized, CacheMiss) and rise_initialized:
            return
        self.log("Initializing Rise Client")
        try:
            register_rise_client()
            self._shared_component_cache.set(key="rise_initialized", value=True)
        except NameError as e:
            msg = "NVIDIA System-Assist is Windows only and not supported on this platform"
            raise ValueError(msg) from e
        except Exception as e:
            msg = f"An error occurred initializing NVIDIA System-Assist: {e}"
            raise ValueError(msg) from e

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

    async def sys_assist_prompt(self) -> Message:
        with contextlib.suppress(ImportError):
            from gassist.rise import send_rise_command

        self.maybe_register_rise_client()

        response = await asyncio.to_thread(send_rise_command, self.prompt)

        return Message(text=response["completed_response"]) if response is not None else Message(text=None)
