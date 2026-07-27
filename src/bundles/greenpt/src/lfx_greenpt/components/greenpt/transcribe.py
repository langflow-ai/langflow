"""GreenPT speech-to-text component."""

from urllib.parse import urlsplit

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.message import Message
from pydantic import SecretStr

LISTEN_URL = "https://api.greenpt.ai/v1/listen"


def _secret_value(value: str | SecretStr) -> str:
    return value.get_secret_value() if isinstance(value, SecretStr) else value


def _transcript(payload: object) -> str:
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
            headers={"Authorization": f"Token {_secret_value(self.api_key)}"},
            params=params,
            json={"url": self.audio_url},
            timeout=120,
        )
        response.raise_for_status()
        text = _transcript(response.json())
        self.status = text
        return Message(text=text)
