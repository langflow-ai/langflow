"""CAMB.AI Voice List component for Langflow."""

from __future__ import annotations

import asyncio

from lfx.custom.custom_component.component import Component
from lfx.io import Output, SecretStrInput
from lfx.schema.data import Data

from ._helpers import get_async_client


class CambVoiceListComponent(Component):
    display_name = "CAMB AI Voice List"
    description = "List all available voices from CAMB.AI."
    icon = "camb-ai"
    name = "CambVoiceList"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="CAMB API Key",
            info="Your CAMB.AI API key.",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Voices", name="voices_output", method="list_voices"),
    ]

    def list_voices(self) -> Data:
        return asyncio.run(self._list_voices_async())

    async def _list_voices_async(self) -> Data:
        client = get_async_client(self.api_key)
        result = await client.voice_cloning.list_voices()

        voices = []
        if result:
            for v in result:
                if isinstance(v, dict):
                    voices.append({"id": v.get("id"), "voice_name": v.get("voice_name", v.get("name", "Unknown"))})
                else:
                    voices.append({"id": getattr(v, "id", None), "voice_name": getattr(v, "voice_name", getattr(v, "name", "Unknown"))})

        self.status = f"Found {len(voices)} voices"
        return Data(data={"voices": voices, "count": len(voices)})
