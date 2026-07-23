from __future__ import annotations

import mimetypes
import os
import stat
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import FileInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.utils.file_path_security import component_file_access_scopes, enforce_local_file_access
from lfx.utils.ssrf_httpx import ssrf_safe_httpx_post


class FunASRTranscriptionComponent(Component):
    display_name = "FunASR Transcription"
    description = "Transcribe audio with a self-hosted FunASR OpenAI-compatible endpoint."
    documentation = "https://www.funasr.com/openai-api.html"
    icon = "AudioLines"

    inputs = [
        FileInput(
            name="audio_file",
            display_name="Audio File",
            file_types=["aac", "amr", "flac", "m4a", "mp3", "mp4", "mpeg", "mpga", "ogg", "opus", "wav", "webm", "wma"],
            info="Upload an audio file to transcribe.",
            required=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="FunASR Base URL",
            value="http://127.0.0.1:8000/v1",
            info=(
                "Base URL or full /audio/transcriptions endpoint. When Langflow SSRF protection is enabled, "
                "add the self-hosted FunASR host to LANGFLOW_SSRF_ALLOWED_HOSTS."
            ),
            required=True,
        ),
        MessageTextInput(
            name="model",
            display_name="Model",
            value="sensevoice",
            info="Model name exposed by the FunASR server.",
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Optional bearer token for an authenticated gateway in front of FunASR.",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="language",
            display_name="Language",
            info="Optional language code forwarded to the transcription endpoint.",
            required=False,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            value=120,
            info="Maximum request time in seconds.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Transcript", name="transcript", method="transcribe"),
    ]

    def _error(self, message: str) -> Data:
        self.status = message
        return Data(data={"error": message})

    def _transcription_url(self) -> str:
        base_url = str(self.base_url or "").strip().rstrip("/")
        if not base_url:
            msg = "FunASR Base URL is required."
            raise ValueError(msg)

        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"}:
            msg = "FunASR Base URL must use http or https."
            raise ValueError(msg)
        if not parsed.hostname:
            msg = "FunASR Base URL must contain a valid host."
            raise ValueError(msg)
        if parsed.username or parsed.password:
            msg = "FunASR Base URL must not contain embedded credentials."
            raise ValueError(msg)
        if parsed.query or parsed.fragment:
            msg = "FunASR Base URL must not contain a query string or fragment."
            raise ValueError(msg)

        if parsed.path.rstrip("/").endswith("/audio/transcriptions"):
            return base_url
        return f"{base_url}/audio/transcriptions"

    def _open_audio_file(self) -> BinaryIO:
        if not self.audio_file:
            msg = "Audio File is required."
            raise ValueError(msg)

        requested_path = Path(self.audio_file)
        scope_ids = component_file_access_scopes(self)
        allowed_path = enforce_local_file_access(requested_path, scope_ids=scope_ids)
        try:
            resolved_path = allowed_path.resolve(strict=True)
            enforce_local_file_access(resolved_path, scope_ids=scope_ids)
        except (OSError, RuntimeError, TypeError, ValueError) as e:
            msg = f"Audio file is not accessible: {e}"
            raise ValueError(msg) from e

        audio_file = None
        try:
            audio_file = requested_path.open("rb")
            opened_stat = os.fstat(audio_file.fileno())
            current_path = requested_path.resolve(strict=True)
            current_path = enforce_local_file_access(current_path, scope_ids=scope_ids)
            current_stat = current_path.stat()
        except (OSError, RuntimeError, TypeError, ValueError) as e:
            if audio_file is not None:
                audio_file.close()
            msg = f"Audio file is not accessible: {e}"
            raise ValueError(msg) from e

        if not stat.S_ISREG(opened_stat.st_mode) or not os.path.samestat(opened_stat, current_stat):
            audio_file.close()
            msg = "Audio file changed while it was being opened."
            raise ValueError(msg)
        return audio_file

    @staticmethod
    def _secret_value(value: object) -> str:
        if value is None:
            return ""
        get_secret_value = getattr(value, "get_secret_value", None)
        if callable(get_secret_value):
            return str(get_secret_value()).strip()
        return str(value).strip()

    def transcribe(self) -> Data:
        try:
            endpoint = self._transcription_url()
            model = str(self.model or "").strip()
            if not model:
                msg = "FunASR model is required."
                raise ValueError(msg)

            timeout = float(self.timeout)
            if timeout <= 0:
                msg = "Timeout must be greater than zero."
                raise ValueError(msg)

            headers = {"Accept": "application/json"}
            api_key = self._secret_value(self.api_key)
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            form_data = {"model": model, "response_format": "json"}
            language = str(self.language or "").strip()
            if language:
                form_data["language"] = language

            with self._open_audio_file() as audio_file:
                filename = Path(self.audio_file).name
                content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                response = ssrf_safe_httpx_post(
                    endpoint,
                    headers=headers,
                    data=form_data,
                    files={"file": (filename, audio_file, content_type)},
                    timeout=timeout,
                )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("text"), str) or not payload["text"].strip():
                msg = "FunASR response is missing a text transcript."
                raise ValueError(msg)

            transcript = payload["text"].strip()
            result = Data(
                text=transcript,
                data={
                    "model": model,
                    "language": language or None,
                    "endpoint": endpoint,
                },
            )
        except httpx.HTTPStatusError as e:
            return self._error(f"FunASR request failed with HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            return self._error(f"FunASR request failed: {e}")
        except (OSError, RuntimeError, TypeError, ValueError) as e:
            return self._error(str(e))
        else:
            self.status = transcript
            return result
