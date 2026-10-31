"""CAMB.AI Translated TTS component for Langflow."""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from ._helpers import add_wav_header, detect_audio_format, get_async_client, poll_task, save_audio


class CambTranslatedTTSComponent(Component):
    display_name = "CAMB AI Translated TTS"
    description = "Translate text and convert to speech in one step using CAMB.AI."
    icon = "camb-ai"
    name = "CambTranslatedTTS"

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
            info="The text to translate and speak.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="source_language",
            display_name="Source Language",
            info="Source language code (integer).",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="target_language",
            display_name="Target Language",
            info="Target language code (integer).",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="voice_id",
            display_name="Voice ID",
            info="Voice ID for TTS output.",
            value=147320,
            tool_mode=True,
        ),
        IntInput(
            name="formality",
            display_name="Formality",
            info="Optional formality: 1=formal, 2=informal.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Audio File Path", name="audio_output", method="translated_tts"),
    ]

    def translated_tts(self) -> Data:
        return asyncio.run(self._translated_tts_async())

    async def _translated_tts_async(self) -> Data:
        import httpx

        client = get_async_client(self.api_key)

        kwargs: dict[str, Any] = {
            "text": self.text,
            "voice_id": self.voice_id,
            "source_language": self.source_language,
            "target_language": self.target_language,
        }
        if self.formality:
            kwargs["formality"] = self.formality

        result = await client.translated_tts.create_translated_tts(**kwargs)
        status = await poll_task(client, client.translated_tts.get_translated_tts_task_status, result.task_id)

        run_id = getattr(status, "run_id", None)
        if run_id is None:
            return Data(data={"error": "Translated TTS task completed but no run_id was returned."})

        # The CAMB SDK doesn't expose a streaming endpoint for translated TTS
        # results, so we fetch the audio directly from the REST API.
        url = f"https://client.camb.ai/apis/tts-result/{run_id}"
        async with httpx.AsyncClient() as http:
            resp = await http.get(url, headers={"x-api-key": self.api_key})
            if resp.status_code != 200:
                return Data(data={"error": f"Failed to fetch TTS audio: HTTP {resp.status_code}"})
            audio_data = resp.content

        if not audio_data:
            return Data(data={"error": "TTS result returned empty audio data."})

        fmt = detect_audio_format(audio_data)
        if fmt == "wav" and audio_data[:4] != b"RIFF":
            audio_data = add_wav_header(audio_data)

        file_path = save_audio(audio_data, "wav")
        self.status = f"Audio saved to {file_path}"
        return Data(data={"file_path": file_path, "format": "wav"})
