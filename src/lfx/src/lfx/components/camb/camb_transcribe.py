"""CAMB.AI Transcription component for Langflow."""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import FileInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from ._helpers import get_async_client, poll_task


class CambTranscribeComponent(Component):
    display_name = "CAMB AI Transcribe"
    description = "Transcribe audio to text with speaker identification using CAMB.AI."
    icon = "camb-ai"
    name = "CambTranscribe"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="CAMB API Key",
            info="Your CAMB.AI API key.",
            required=True,
        ),
        IntInput(
            name="language",
            display_name="Language",
            info="Language code (integer). 1=English, 2=Spanish, 3=French, etc.",
            required=True,
            tool_mode=True,
        ),
        FileInput(
            name="audio_file",
            display_name="Audio File",
            file_types=["wav", "mp3", "flac", "ogg", "m4a", "webm"],
            info="The audio file to transcribe.",
        ),
        MessageTextInput(
            name="audio_url",
            display_name="Audio URL",
            info="URL of the audio file to transcribe (alternative to file upload).",
            advanced=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Transcription", name="transcription_output", method="transcribe_audio"),
    ]

    def transcribe_audio(self) -> Data:
        return asyncio.run(self._transcribe_async())

    async def _transcribe_async(self) -> Data:
        client = get_async_client(self.api_key)

        kwargs: dict[str, Any] = {"language": self.language}

        if self.audio_file:
            with open(self.audio_file, "rb") as f:
                kwargs["media_file"] = f
                result = await client.transcription.create_transcription(**kwargs)
        elif self.audio_url:
            kwargs["media_url"] = self.audio_url
            result = await client.transcription.create_transcription(**kwargs)
        else:
            return Data(data={"error": "Provide either an audio file or audio URL"})

        task_id = result.task_id
        status = await poll_task(client, client.transcription.get_transcription_task_status, task_id)
        transcription = await client.transcription.get_transcription_result(status.run_id)

        segments = []
        if hasattr(transcription, "transcript") and transcription.transcript:
            for seg in transcription.transcript:
                segments.append(
                    {
                        "start": getattr(seg, "start", 0),
                        "end": getattr(seg, "end", 0),
                        "text": getattr(seg, "text", ""),
                        "speaker": getattr(seg, "speaker", ""),
                    }
                )

        full_text = " ".join(s["text"] for s in segments)
        if not full_text.strip():
            return Data(data={"text": "", "segments": [], "warning": "Transcription returned no text"})
        self.status = full_text[:200] + "..." if len(full_text) > 200 else full_text
        return Data(data={"text": full_text, "segments": segments})
