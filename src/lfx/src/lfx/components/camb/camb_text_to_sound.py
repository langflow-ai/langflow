"""CAMB.AI Text-to-Sound component for Langflow."""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from ._helpers import get_async_client, poll_task, save_audio


class CambTextToSoundComponent(Component):
    display_name = "CAMB AI Text-to-Sound"
    description = "Generate sounds, music, or soundscapes from text descriptions using CAMB.AI."
    icon = "camb-ai"
    name = "CambTextToSound"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="CAMB API Key",
            info="Your CAMB.AI API key.",
            required=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            info="Description of the sound or music to generate.",
            required=True,
            tool_mode=True,
        ),
        FloatInput(
            name="duration",
            display_name="Duration (seconds)",
            info="Optional duration of the generated audio in seconds.",
            advanced=True,
        ),
        DropdownInput(
            name="audio_type",
            display_name="Audio Type",
            options=["music", "sound"],
            info="Optional type of audio to generate.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Audio File Path", name="audio_output", method="generate_sound"),
    ]

    def generate_sound(self) -> Data:
        return asyncio.run(self._generate_sound_async())

    async def _generate_sound_async(self) -> Data:
        client = get_async_client(self.api_key)

        kwargs: dict[str, Any] = {"prompt": self.prompt}
        if self.duration:
            kwargs["duration"] = self.duration
        if self.audio_type:
            kwargs["audio_type"] = self.audio_type

        task = await client.text_to_audio.create_text_to_audio(**kwargs)
        status = await poll_task(client, client.text_to_audio.get_text_to_audio_status, task.task_id)

        chunks: list[bytes] = []
        async for chunk in client.text_to_audio.get_text_to_audio_result(status.run_id):
            chunks.append(chunk)

        audio_data = b"".join(chunks)
        if not audio_data:
            return Data(data={"error": "Text-to-sound returned no audio data"})

        file_path = save_audio(audio_data, "wav")
        self.status = f"Audio saved to {file_path}"
        return Data(data={"file_path": file_path, "format": "wav"})
