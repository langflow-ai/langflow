"""CAMB.AI Voice Clone component for Langflow."""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FileInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from ._helpers import get_async_client


class CambVoiceCloneComponent(Component):
    display_name = "CAMB AI Voice Clone"
    description = "Clone a voice from an audio sample using CAMB.AI."
    icon = "camb-ai"
    name = "CambVoiceClone"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="CAMB API Key",
            info="Your CAMB.AI API key.",
            required=True,
        ),
        MessageTextInput(
            name="voice_name",
            display_name="Voice Name",
            info="Name for the cloned voice.",
            required=True,
            tool_mode=True,
        ),
        FileInput(
            name="audio_file",
            display_name="Audio File",
            file_types=["wav", "mp3", "flac", "ogg", "m4a"],
            info="Audio file (minimum 2 seconds) to clone the voice from.",
            required=True,
        ),
        DropdownInput(
            name="gender",
            display_name="Gender",
            options=["Not Specified", "Male", "Female", "Not Applicable"],
            value="Not Specified",
            info="Gender of the voice.",
        ),
        MessageTextInput(
            name="description",
            display_name="Description",
            info="Optional description of the voice.",
            advanced=True,
        ),
        IntInput(
            name="age",
            display_name="Age",
            info="Optional age of the voice.",
            advanced=True,
        ),
        IntInput(
            name="language",
            display_name="Language Code",
            info="Optional language code for the voice.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Voice Info", name="voice_output", method="clone_voice"),
    ]

    _GENDER_MAP = {"Not Specified": 0, "Male": 1, "Female": 2, "Not Applicable": 9}

    def clone_voice(self) -> Data:
        return asyncio.run(self._clone_voice_async())

    async def _clone_voice_async(self) -> Data:
        client = get_async_client(self.api_key)
        gender_code = self._GENDER_MAP.get(self.gender, 0)

        with open(self.audio_file, "rb") as f:
            kwargs: dict[str, Any] = {
                "voice_name": self.voice_name,
                "gender": gender_code,
                "file": f,
            }
            if self.description:
                kwargs["description"] = self.description
            if self.age:
                kwargs["age"] = self.age
            if self.language:
                kwargs["language"] = self.language
            result = await client.voice_cloning.create_custom_voice(**kwargs)

        voice_id = getattr(result, "voice_id", getattr(result, "id", None))
        if voice_id is None:
            return Data(data={"error": "Voice clone succeeded but no voice_id was returned"})
        self.status = f"Voice cloned: {self.voice_name} (ID: {voice_id})"
        return Data(data={"voice_id": voice_id, "voice_name": self.voice_name, "status": "created"})
