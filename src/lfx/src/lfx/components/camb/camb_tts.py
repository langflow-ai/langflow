"""CAMB.AI Text-to-Speech component for Langflow."""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from ._helpers import get_async_client, save_audio


class CambTTSComponent(Component):
    display_name = "CAMB AI Text-to-Speech"
    description = "Convert text to speech using CAMB.AI. Supports 140+ languages and multiple voice models."
    icon = "camb-ai"
    name = "CambTTS"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="CAMB API Key",
            info="Your CAMB.AI API key.",
            required=True,
        ),
        MessageTextInput(
            name="text",
            display_name="Text",
            info="The text to convert to speech (3-3000 characters).",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="language",
            display_name="Language",
            info="BCP-47 language code (e.g. 'en-us', 'fr-fr').",
            value="en-us",
            tool_mode=True,
        ),
        IntInput(
            name="voice_id",
            display_name="Voice ID",
            info="Voice ID for speech synthesis. Use CAMB Voice List to find voices.",
            value=147320,
            tool_mode=True,
        ),
        DropdownInput(
            name="speech_model",
            display_name="Speech Model",
            options=["mars-flash", "mars-pro", "mars-instruct"],
            value="mars-flash",
            info="The speech model to use.",
        ),
        MessageTextInput(
            name="user_instructions",
            display_name="User Instructions",
            info="Optional instructions for the mars-instruct model.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Audio File Path", name="audio_output", method="generate_speech"),
    ]

    def generate_speech(self) -> Data:
        result = asyncio.run(self._generate_speech_async())
        return result

    async def _generate_speech_async(self) -> Data:
        from camb import StreamTtsOutputConfiguration

        client = get_async_client(self.api_key)

        kwargs: dict[str, Any] = {
            "text": self.text,
            "language": self.language,
            "voice_id": self.voice_id,
            "speech_model": self.speech_model,
            "output_configuration": StreamTtsOutputConfiguration(format="wav"),
        }
        if self.user_instructions and self.speech_model == "mars-instruct":
            kwargs["user_instructions"] = self.user_instructions

        chunks: list[bytes] = []
        async for chunk in client.text_to_speech.tts(**kwargs):
            chunks.append(chunk)

        audio_data = b"".join(chunks)
        if not audio_data:
            return Data(data={"error": "TTS returned no audio data"})

        file_path = save_audio(audio_data, "wav")
        self.status = f"Audio saved to {file_path}"
        return Data(data={"file_path": file_path, "format": "wav"})
