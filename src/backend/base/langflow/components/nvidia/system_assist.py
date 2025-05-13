import asyncio
import time

from gassist.rise import register_rise_client, send_rise_command

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
    )
    documentation = "https://docs.langflow.org/components-custom-components"
    icon = "NVIDIA"
    rise_initialized = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def maybe_register_rise_client(self):
        rise_initialized = self._shared_component_cache.get("rise_initialized")
        if not isinstance(rise_initialized, CacheMiss) and rise_initialized:
            return
        self.log("Initializing Rise Client")
        try:
            register_rise_client()
            self._shared_component_cache.set(key="rise_initialized", value=True)
        except Exception as e:
            msg = f"An error occurred initializing rise client: {e}"
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
        # Add timing debug logs with print()
        start_time = time.time()
        print(f"[DEBUG] Starting sys_assist_prompt at {start_time}")

        # Wrap the blocking send_rise_command call in a thread to avoid blocking the event loop.
        self.maybe_register_rise_client()
        print(f"[DEBUG] After register_rise_client: {time.time() - start_time:.4f}s")

        response = await asyncio.to_thread(send_rise_command, self.prompt)
        print(f"[DEBUG] After send_rise_command: {time.time() - start_time:.4f}s")

        if response is not None:
            result = Message(text=response["completed_response"])
        else:
            result = Message(text=None)

        print(f"[DEBUG] Completed sys_assist_prompt in {time.time() - start_time:.4f}s")
        return result
