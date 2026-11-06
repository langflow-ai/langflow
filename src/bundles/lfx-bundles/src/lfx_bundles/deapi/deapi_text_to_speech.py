"""Turn text into speech with deAPI."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.schema.data import Data

from lfx_bundles.deapi.deapi_common import (
    API_KEY_INFO,
    DOCUMENTATION_URL,
    DeapiAPIError,
    error_payload,
    find_model,
    job_payload,
    model_info,
    model_slugs,
    run_job,
)

INFERENCE_TYPE = "txt2audio"
# Shown until the live catalog loads (it refreshes once an API key is set).
FALLBACK_MODELS = ["Kokoro", "Chatterbox", "Qwen3_TTS_12Hz_1_7B_CustomVoice"]


class DeapiTextToSpeechComponent(Component):
    """Generate speech through deAPI and return the audio URL.

    The API needs a voice, language, speed, format and sample rate for every request;
    any left empty here come from the selected model's published defaults.
    """

    display_name = "deAPI Text to Speech"
    description = "Turn text into natural speech with open-source voice models on deAPI, such as Kokoro."
    documentation = DOCUMENTATION_URL
    icon = "deAPI"
    name = "DeapiTextToSpeech"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="deAPI API Key",
            info=API_KEY_INFO,
            required=True,
            value="DEAPI_API_KEY",
            real_time_refresh=True,
        ),
        MultilineInput(
            name="text",
            display_name="Text",
            info="The text to read aloud.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The deAPI voice model to use. The list shows the text-to-speech models available to your account.",
            options=FALLBACK_MODELS,
            value=FALLBACK_MODELS[0],
            refresh_button=True,
            combobox=True,
        ),
        MessageTextInput(
            name="voice",
            display_name="Voice",
            info="The voice name, such as af_alloy for Kokoro. Leave empty to use the model's default voice.",
            advanced=True,
        ),
        MessageTextInput(
            name="language",
            display_name="Language",
            info="The language code the model expects, such as en-us for Kokoro. "
            "Leave empty to use the model's default.",
            advanced=True,
        ),
        FloatInput(
            name="speed",
            display_name="Speed",
            info="Speaking speed, where 1 is normal. Leave at 0 to use the model's default.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="max_wait",
            display_name="Max Wait (seconds)",
            info="How long to wait for the audio before returning the job's request ID.",
            value=180,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Audio", name="audio", method="generate_speech"),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Reload the model list from the live catalog when the key changes or Refresh is pressed."""
        if field_name in {"api_key", "model_name"}:
            build_config["model_name"]["options"] = model_slugs(self.api_key, INFERENCE_TYPE, FALLBACK_MODELS)
        return build_config

    def build_payload(self) -> dict[str, Any]:
        """Build the request body, filling voice, language, speed, format and rate from the model."""
        text = str(self.text or "").strip()
        if not text:
            msg = "Enter the text to read aloud."
            raise DeapiAPIError(msg)
        model = str(self.model_name or "").strip()
        if not model:
            msg = "Choose a model."
            raise DeapiAPIError(msg)
        defaults, limits = model_info(find_model(self.api_key, INFERENCE_TYPE, model))
        speed = float(self.speed) if self.speed else float(defaults.get("speed") or 1)
        if isinstance(limits.get("min_speed"), int | float):
            speed = max(speed, float(limits["min_speed"]))
        if isinstance(limits.get("max_speed"), int | float):
            speed = min(speed, float(limits["max_speed"]))
        formats = limits.get("output_formats") or []
        rates = limits.get("available_ratios") or []
        return {
            "text": text,
            "model": model,
            "voice": str(self.voice or "").strip() or defaults.get("voice") or "default",
            "lang": str(self.language or "").strip() or defaults.get("lang") or "en",
            "speed": speed,
            "format": defaults.get("format") or (formats[0] if formats else "mp3"),
            "sample_rate": defaults.get("sample_rate") or (rates[0] if rates else 24000),
        }

    def generate_speech(self) -> Data:
        """Return the speech as a ``Data`` whose ``text`` is the audio URL (also under ``audio_url``)."""
        try:
            job = run_job("/audio/speech", self.build_payload(), api_key=self.api_key, max_wait_seconds=self.max_wait)
        except DeapiAPIError as exc:
            payload = error_payload(str(exc))
        else:
            payload = job_payload(job, kind="speech", url_key="audio_url")
        self.status = payload["text"]
        return Data(data=payload)
