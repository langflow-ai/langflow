"""Transcribe a YouTube, X, TikTok, Twitch or Kick video or audio link with deAPI."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.message import Message

from lfx_bundles.deapi.deapi_common import (
    API_KEY_INFO,
    DOCUMENTATION_URL,
    DeapiAPIError,
    error_payload,
    job_payload,
    model_slugs,
    run_job,
)

INFERENCE_TYPE = "video2text"
# Shown until the live catalog loads (it refreshes once an API key is set).
FALLBACK_MODELS = ["WhisperLargeV3", "WhisperLargeV3Ct2"]
SUPPORTED_SITES = "YouTube, X, TikTok, Twitch and Kick"


class DeapiTranscriptionComponent(Component):
    """Transcribe the speech in a public video or audio link through deAPI.

    deAPI downloads the media on its own servers, so this component only sends the
    link to ``api.deapi.ai`` and never opens a connection to the media itself.
    """

    display_name = "deAPI Transcription"
    description = f"Transcribe a {SUPPORTED_SITES} link to text with Whisper models on deAPI."
    documentation = DOCUMENTATION_URL
    icon = "deAPI"
    name = "DeapiTranscription"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="deAPI API Key",
            info=API_KEY_INFO,
            required=True,
            value="DEAPI_API_KEY",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="media_url",
            display_name="Media Link",
            info=f"A public {SUPPORTED_SITES} link, such as https://www.youtube.com/watch?v=... "
            "Direct links to media files are not supported.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The deAPI transcription model to use.",
            options=FALLBACK_MODELS,
            value=FALLBACK_MODELS[0],
            refresh_button=True,
            combobox=True,
        ),
        BoolInput(
            name="include_timestamps",
            display_name="Include Timestamps",
            info="Add segment timestamps to the transcript.",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="max_wait",
            display_name="Max Wait (seconds)",
            info="How long to wait for the transcript before returning the job's request ID.",
            value=300,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Transcript", name="transcript", method="transcribe"),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Reload the model list from the live catalog when the key changes or Refresh is pressed."""
        if field_name in {"api_key", "model_name"}:
            build_config["model_name"]["options"] = model_slugs(self.api_key, INFERENCE_TYPE, FALLBACK_MODELS)
        return build_config

    def build_payload(self) -> dict[str, Any]:
        """Build the request body after checking the link is an absolute http(s) URL."""
        url = str(self.media_url or "").strip()
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        except ValueError:  # e.g. an unmatched bracket in the host
            valid = False
        if not valid:
            msg = f"Enter an absolute http(s) {SUPPORTED_SITES} link; got {url!r}."
            raise DeapiAPIError(msg)
        model = str(self.model_name or "").strip()
        if not model:
            msg = "Choose a model."
            raise DeapiAPIError(msg)
        return {
            "model": model,
            "source_url": url,
            "include_ts": bool(self.include_timestamps),
            "return_result_in_response": True,
        }

    def transcribe(self) -> Message:
        """Return the transcript, or the error, as a ``Message``."""
        try:
            job = run_job(
                "/audio/transcriptions", self.build_payload(), api_key=self.api_key, max_wait_seconds=self.max_wait
            )
        except DeapiAPIError as exc:
            payload = error_payload(str(exc))
        else:
            payload = job_payload(job, kind="transcription")
        self.status = payload["text"]
        return Message(text=payload["text"])
