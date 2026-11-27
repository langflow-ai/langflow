from __future__ import annotations

import asyncio
import base64
import io
import wave
from typing import Any

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.utils.ssrf_httpx import ssrf_safe_strict_httpx_post

from lfx_bundles.lokutor.lokutor_common import (
    AUTO_LANGUAGE,
    DEFAULT_BASE_URL,
    DOCUMENTATION_URL,
    LANGUAGES,
    VOICES,
    api_url,
    error_message,
    require_api_key,
)

MAX_TEXT_CHARS = 10_000


def _wav_stats(audio: bytes) -> dict[str, Any]:
    """Return sample rate and duration for a WAV payload; empty when it cannot be parsed."""
    try:
        with wave.open(io.BytesIO(audio), "rb") as reader:
            rate = reader.getframerate()
            frames = reader.getnframes()
    except (wave.Error, EOFError):
        return {}
    return {"sample_rate": rate, "duration_seconds": round(frames / rate, 3) if rate else None}


class LokutorTextToSpeechComponent(Component):
    display_name = "Lokutor Text to Speech"
    description = "Turn text into speech with Lokutor's own speech models (nine languages, ten voices)."
    documentation = f"{DOCUMENTATION_URL}/api-reference/rest.md"
    icon = "AudioLines"
    name = "LokutorTextToSpeech"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Lokutor API Key",
            info="Your Lokutor API key. Create one at https://app.lokutor.com.",
            required=True,
        ),
        MessageTextInput(
            name="text",
            display_name="Text",
            info="The text to speak. Connect a Chat Input, a prompt or a model's reply.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="voice",
            display_name="Voice",
            info="A voice slot (F1-F5, M1-M5) or the id of one of your cloned voices (clone_...).",
            options=VOICES,
            value="F1",
            combobox=True,
        ),
        DropdownInput(
            name="language",
            display_name="Language",
            info=(
                "Language of the text. Pass it for predictable results: without a hint the voice speaks "
                "with the English speaker."
            ),
            options=[AUTO_LANGUAGE, *LANGUAGES],
            value="en",
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            info="How varied the delivery is, 0.1 to 1.0. Leave empty for the server default (0.3).",
            advanced=True,
            required=False,
        ),
        MessageTextInput(
            name="base_url",
            display_name="Lokutor Base URL",
            info="API base URL. Leave the default unless you proxy Lokutor.",
            value=DEFAULT_BASE_URL,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Maximum request time in seconds.",
            value=120,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Audio", name="audio", method="synthesize", types=["Data"]),
    ]

    def _text_value(self) -> str:
        value = self.text
        text = getattr(value, "text", value)
        text = str(text or "").strip()
        if not text:
            msg = "Text is required."
            raise ValueError(msg)
        if len(text) > MAX_TEXT_CHARS:
            msg = f"Text is longer than {MAX_TEXT_CHARS} characters; split it and synthesize the parts."
            raise ValueError(msg)
        return text

    def _request(self) -> tuple[str, dict[str, str], dict[str, Any], float]:
        base_url = str(self.base_url or "").strip()
        endpoint = api_url(base_url, "tts/synthesize")
        key = require_api_key(self.api_key, base_url)
        voice = str(self.voice or "").strip() or "F1"
        payload: dict[str, Any] = {"text": self._text_value(), "voice": voice}
        language = str(self.language or "").strip()
        if language and language != AUTO_LANGUAGE:
            payload["language"] = language
        if self.temperature not in (None, ""):
            payload["temperature"] = float(self.temperature)
        timeout = float(self.timeout)
        if timeout <= 0:
            msg = "Timeout must be greater than zero."
            raise ValueError(msg)
        headers = {"Authorization": f"Bearer {key}", "Accept": "audio/wav"}
        return endpoint, headers, payload, timeout

    async def synthesize(self) -> Data:
        endpoint, headers, payload, timeout = self._request()
        try:
            response = await asyncio.to_thread(
                lambda: ssrf_safe_strict_httpx_post(endpoint, headers=headers, json=payload, timeout=timeout)
            )
        except httpx.RequestError as e:
            msg = f"Lokutor request failed: {type(e).__name__}: {e}"
            raise ValueError(msg) from e
        if not response.is_success:
            raise ValueError(error_message(response))
        audio = response.content
        if not audio:
            msg = "Lokutor returned no audio."
            raise ValueError(msg)

        details: dict[str, Any] = {
            "audio_base64": base64.b64encode(audio).decode("ascii"),
            "mime_type": "audio/wav",
            "format": "wav",
            "size_bytes": len(audio),
            "voice": payload["voice"],
            "language": payload.get("language"),
            "characters": len(payload["text"]),
            **_wav_stats(audio),
        }
        self.status = f"{details['size_bytes']} bytes of WAV audio, voice {details['voice']}"
        return Data(text=payload["text"], data=details)
