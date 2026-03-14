"""CAMB.AI Audio Separation component for Langflow."""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import FileInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from ._helpers import get_async_client, poll_task


class CambAudioSeparationComponent(Component):
    display_name = "CAMB AI Audio Separation"
    description = "Separate vocals from background audio using CAMB.AI."
    icon = "camb-ai"
    name = "CambAudioSeparation"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="CAMB API Key",
            info="Your CAMB.AI API key.",
            required=True,
        ),
        FileInput(
            name="audio_file",
            display_name="Audio File",
            file_types=["wav", "mp3", "flac", "ogg", "m4a"],
            info="The audio file to separate.",
        ),
        MessageTextInput(
            name="audio_url",
            display_name="Audio URL",
            info="URL of the audio file to separate (alternative to file upload).",
            advanced=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Separation Result", name="separation_output", method="separate_audio"),
    ]

    def separate_audio(self) -> Data:
        return asyncio.run(self._separate_audio_async())

    async def _separate_audio_async(self) -> Data:
        client = get_async_client(self.api_key)
        kwargs: dict[str, Any] = {}

        if self.audio_file:
            with open(self.audio_file, "rb") as f:
                kwargs["media_file"] = f
                task = await client.audio_separation.create_audio_separation(**kwargs)
        elif self.audio_url:
            kwargs["media_url"] = self.audio_url
            task = await client.audio_separation.create_audio_separation(**kwargs)
        else:
            return Data(data={"error": "Provide either an audio file or audio URL"})

        status = await poll_task(client, client.audio_separation.get_audio_separation_status, task.task_id)
        result = await client.audio_separation.get_audio_separation_run_info(status.run_id)

        output = {
            "foreground_audio_url": getattr(result, "foreground_audio_url", None),
            "background_audio_url": getattr(result, "background_audio_url", None),
        }
        self.status = "Audio separation complete"
        return Data(data=output)
