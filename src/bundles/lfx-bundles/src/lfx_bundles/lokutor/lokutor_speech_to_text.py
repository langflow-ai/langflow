from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, FileInput, HandleInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.utils.ssrf_httpx import ssrf_safe_strict_httpx_post

from lfx_bundles.lokutor.lokutor_common import (
    AUTO_LANGUAGE,
    DEFAULT_BASE_URL,
    DOCUMENTATION_URL,
    LANGUAGES,
    api_url,
    error_message,
    read_scoped_file,
    require_api_key,
)

MIN_SPEAKERS, MAX_SPEAKERS = 1, 32
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # the API refuses larger files without diarization


class LokutorSpeechToTextComponent(Component):
    display_name = "Lokutor Speech to Text"
    description = "Transcribe a WAV recording with Lokutor's own speech recognition (nine languages)."
    documentation = f"{DOCUMENTATION_URL}/api-reference/speech-to-text.md"
    icon = "AudioLines"
    name = "LokutorSpeechToText"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Lokutor API Key",
            info="Your Lokutor API key. Create one at https://app.lokutor.com.",
            required=True,
        ),
        FileInput(
            name="audio_file",
            display_name="Audio File",
            file_types=["wav"],
            info="A WAV recording (PCM 8 or 16 bit, 8 to 48 kHz, up to 10 MB). Other formats are not decoded yet.",
            required=False,
        ),
        HandleInput(
            name="audio_data",
            display_name="Audio Data",
            input_types=["Data"],
            info="Audio from another component, such as Lokutor Text to Speech. Used when no file is uploaded.",
            required=False,
        ),
        DropdownInput(
            name="language",
            display_name="Language",
            info="Language of the recording, or auto to detect it.",
            options=[AUTO_LANGUAGE, *LANGUAGES],
            value=AUTO_LANGUAGE,
        ),
        BoolInput(
            name="diarize",
            display_name="Label Speakers",
            info="Label each word with the speaker who said it (speaker_0, speaker_1, ...).",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="num_speakers",
            display_name="Number of Speakers",
            info="1 to 32. Improves diarization when you know it. Only used when Label Speakers is on.",
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
            value=300,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Transcript", name="transcript", method="transcribe_message", types=["Message"]),
        Output(display_name="Details", name="details", method="transcribe_details", types=["Data"]),
    ]

    _cache: tuple[str, dict[str, Any]] | None = None

    def _audio_bytes(self) -> tuple[bytes, str]:
        if self.audio_file:
            path = str(self.audio_file)
            return read_scoped_file(path, component=self), Path(path).name or "audio.wav"
        data = self.audio_data
        if isinstance(data, list):
            data = data[0] if data else None
        payload = getattr(data, "data", data)
        encoded = payload.get("audio_base64") if isinstance(payload, dict) else None
        if not encoded:
            msg = "Provide an Audio File or connect Audio Data that carries audio_base64."
            raise ValueError(msg)
        try:
            return base64.b64decode(encoded, validate=True), "audio.wav"
        except (binascii.Error, ValueError) as e:
            msg = "Audio Data does not contain valid base64 audio."
            raise ValueError(msg) from e

    def _request(self) -> tuple[str, dict[str, str], dict[str, str], float]:
        base_url = str(self.base_url or "").strip()
        endpoint = api_url(base_url, "speech-to-text")
        key = require_api_key(self.api_key, base_url)
        timeout = float(self.timeout)
        if timeout <= 0:
            msg = "Timeout must be greater than zero."
            raise ValueError(msg)
        form = {"timestamps_granularity": "word"}
        language = str(self.language or "").strip()
        if language and language != AUTO_LANGUAGE:
            form["language_code"] = language
        if self.diarize:
            form["diarize"] = "true"
            if self.num_speakers not in (None, ""):
                speakers = int(self.num_speakers)
                if not MIN_SPEAKERS <= speakers <= MAX_SPEAKERS:
                    msg = "Number of Speakers must be between 1 and 32."
                    raise ValueError(msg)
                form["num_speakers"] = str(speakers)
        return endpoint, {"Authorization": f"Bearer {key}", "Accept": "application/json"}, form, timeout

    async def _transcribe(self) -> dict[str, Any]:
        """Call the API once per distinct request; both outputs share the result so a run is billed once."""
        endpoint, headers, form, timeout = self._request()
        audio, filename = self._audio_bytes()
        if not audio:
            msg = "The audio is empty."
            raise ValueError(msg)
        if len(audio) > MAX_UPLOAD_BYTES and not self.diarize:
            msg = "Audio is larger than 10 MB; Lokutor accepts bigger files only with Label Speakers on."
            raise ValueError(msg)
        fingerprint = hashlib.sha256(
            audio + json.dumps([endpoint, sorted(form.items())]).encode() + headers["Authorization"].encode()
        ).hexdigest()
        if self._cache and self._cache[0] == fingerprint:
            return self._cache[1]
        try:
            response = await asyncio.to_thread(
                lambda: ssrf_safe_strict_httpx_post(
                    endpoint,
                    headers=headers,
                    data=form,
                    files={"file": (filename, audio, "audio/wav")},
                    timeout=timeout,
                )
            )
        except httpx.RequestError as e:
            msg = f"Lokutor request failed: {type(e).__name__}: {e}"
            raise ValueError(msg) from e
        if response.status_code >= httpx.codes.BAD_REQUEST:
            raise ValueError(error_message(response))
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
            msg = "Lokutor response is missing a text transcript."
            raise TypeError(msg)
        self._cache = (fingerprint, payload)
        self.status = payload["text"]
        return payload

    async def transcribe_message(self) -> Message:
        result = await self._transcribe()
        return Message(text=result["text"].strip())

    async def transcribe_details(self) -> Data:
        result = await self._transcribe()
        words = [w for w in result.get("words") or [] if isinstance(w, dict) and w.get("type") != "spacing"]
        return Data(
            text=result["text"].strip(),
            data={
                "language_code": result.get("language_code"),
                "language_probability": result.get("language_probability"),
                "words": words,
            },
        )
