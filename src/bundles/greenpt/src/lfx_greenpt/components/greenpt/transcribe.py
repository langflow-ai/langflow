"""GreenPT speech-to-text component."""

from urllib.parse import urlsplit

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.message import Message
from lfx_greenpt._utils import secret_value
from lfx_greenpt.models import GREENPT_BASE_URL

LISTEN_URL = f"{GREENPT_BASE_URL}/listen"


def _transcript(payload: object) -> str:
    """Extract a non-empty transcript from a GreenPT response."""
    try:
        transcript = payload["results"]["channels"][0]["alternatives"][0]["transcript"]  # type: ignore[index]
    except (KeyError, IndexError, TypeError) as e:
        msg = "GreenPT returned an invalid speech-to-text response."
        raise ValueError(msg) from e
    if not isinstance(transcript, str) or not transcript.strip():
        msg = "GreenPT returned an invalid speech-to-text transcript."
        raise TypeError(msg)
    return transcript.strip()


class GreenPTSpeechToTextComponent(Component):
    """Transcribe public audio URLs through GreenPT."""

    display_name = "GreenPT Speech to Text"
    description = "Transcribe public audio URLs with GreenPT's renewable-powered optimized AI infrastructure."
    name = "GreenPTSpeechToText"
    icon = "GreenPT"
    documentation = "https://docs.greenpt.ai"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="GreenPT API Key",
            value="GREENPT_API_KEY",
            required=True,
        ),
        MessageTextInput(
            name="audio_url",
            display_name="Audio URL",
            info="A public HTTP or HTTPS URL for the audio file.",
            required=True,
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            options=["green-s-pro", "green-s"],
            value="green-s-pro",
            info="green-s-pro is GreenS Pro; green-s is GreenS.",
        ),
        StrInput(
            name="language",
            display_name="Language",
            info="Optional BCP-47 language code, for example en or nl.",
            advanced=True,
        ),
        BoolInput(name="punctuate", display_name="Punctuate", value=True, advanced=True),
        BoolInput(name="smart_format", display_name="Smart Format", value=True, advanced=True),
    ]

    outputs = [Output(display_name="Transcript", name="transcript", method="transcribe")]

    def transcribe(self) -> Message:
        """Transcribe a public audio URL with GreenPT."""
        parsed = urlsplit(self.audio_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            msg = "Audio URL must be a public HTTP or HTTPS URL without embedded credentials."
            raise ValueError(msg)

        params: dict[str, str | bool] = {
            "model": self.model,
            "punctuate": self.punctuate,
            "smart_format": self.smart_format,
        }
        if self.language:
            params["language"] = self.language
        response = httpx.post(
            LISTEN_URL,
            headers={"Authorization": f"Token {secret_value(self.api_key)}"},
            params=params,
            json={"url": self.audio_url},
            timeout=120,
        )
        response.raise_for_status()
        text = _transcript(response.json())
        self.status = text
        return Message(text=text)
