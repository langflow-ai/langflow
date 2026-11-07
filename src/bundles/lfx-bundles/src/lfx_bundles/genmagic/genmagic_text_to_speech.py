"""Turn text into speech with GenMagic."""

from __future__ import annotations

import base64
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message

from lfx_bundles.genmagic.genmagic_common import (
    API_KEY_INFO,
    API_KEY_VARIABLE,
    AUTO_MODEL,
    DOCUMENTATION_URL,
    GenMagicAPIError,
    call_api,
    chosen_model,
    metering,
    positive_seconds,
    refresh_model_dropdown,
    text_value,
)

DEFAULT_VOICE = "alloy"
SPEECH_TIMEOUT_SECONDS = 120
# Without a hosted URL the audio is returned inline; a clip larger than this is not, to keep the output small.
MAX_INLINE_AUDIO_BYTES = 8 * 1024 * 1024


def is_speech_model(model: dict[str, Any]) -> bool:
    """Whether a catalog audio entry speaks text (the audio catalog also lists music models)."""
    return model.get("audio_kind") in {None, "speech"}


class GenMagicTextToSpeechComponent(Component):
    """Speak text with a GenMagic text-to-speech model and return the hosted audio URL."""

    display_name = "GenMagic Text to Speech"
    description = "Turn text into spoken audio with any GenMagic text-to-speech model."
    documentation = DOCUMENTATION_URL
    icon = "GenMagic"
    name = "GenMagicTextToSpeech"

    # The request and result of this build, shared by every connected output (see _pre_run_setup).
    _speech: tuple[dict[str, Any], dict[str, Any]] | None = None

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="GenMagic API Key",
            info=API_KEY_INFO,
            value=API_KEY_VARIABLE,
            required=True,
        ),
        MessageTextInput(
            name="text",
            display_name="Text",
            info="The text to speak. It is voiced verbatim.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info=f"The text-to-speech model. {AUTO_MODEL} lets GenMagic pick its recommended model. "
            "The list loads from the live GenMagic catalog; type a model ID to use one that is not listed.",
            options=[],
            value=AUTO_MODEL,
            combobox=True,
            refresh_button=True,
        ),
        MessageTextInput(
            name="voice",
            display_name="Voice",
            info="The voice name, for example alloy. Leave empty for the model's default voice.",
            value=DEFAULT_VOICE,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for GenMagic to answer.",
            value=SPEECH_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Audio URL", name="audio_url", method="build_audio_url", tool_mode=False),
        Output(display_name="Result", name="result", method="build_result"),
    ]

    def _pre_run_setup(self) -> None:
        # One paid request per build, shared by every output that is connected.
        self._speech = None

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Load the text-to-speech models from the live GenMagic catalog (a public endpoint that needs no key)."""
        if field_name not in {None, "model_name"}:
            return build_config
        return refresh_model_dropdown(build_config, "model_name", "audio", include_auto=True, keep=is_speech_model)

    def _request_body(self) -> dict[str, Any]:
        text = text_value(self.text)
        if not text:
            msg = "Enter the text to speak."
            raise GenMagicAPIError(msg)
        body: dict[str, Any] = {"input": text}
        if model := chosen_model(self.model_name):
            body["model"] = model
        if voice := text_value(self.voice):
            body["voice"] = voice
        return body

    def speak(self) -> dict[str, Any]:
        """Run the request once and return the hosted ``audio_url`` with its model, voice and cost."""
        body = self._request_body()
        cached = self._speech
        if cached is not None and cached[0] == body:
            return cached[1]
        response = call_api(
            "POST",
            "/audio/speech",
            api_key=self.api_key,
            timeout=positive_seconds(self.timeout, SPEECH_TIMEOUT_SECONDS),
            json=body,
        )
        audio_url = (response.headers.get("X-Media-Url") or "").strip()
        result: dict[str, Any] = {
            "model": body.get("model", AUTO_MODEL),
            "voice": body.get("voice", ""),
            "mime_type": (response.headers.get("Content-Type") or "audio/mpeg").split(";")[0].strip(),
            **metering(response),
        }
        if audio_url:
            result["audio_url"] = audio_url
        elif response.content and len(response.content) <= MAX_INLINE_AUDIO_BYTES:
            # GenMagic always sends a hosted URL; keep what was paid for if it ever does not.
            result["audio_base64"] = base64.b64encode(response.content).decode("ascii")
        else:
            msg = "GenMagic returned no audio."
            raise GenMagicAPIError(msg, status=response.status_code)
        self._speech = (body, result)
        self.status = audio_url or "Audio returned inline as base64."
        return result

    def build_audio_url(self) -> Message:
        """The hosted URL of the audio, to wire into another component."""
        return Message(text=self.speak().get("audio_url", ""))

    def build_result(self) -> Data:
        """The audio URL, model, voice, MIME type and what the call cost."""
        return Data(data=self.speak())
