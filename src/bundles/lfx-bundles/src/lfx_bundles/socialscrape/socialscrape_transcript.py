"""Get the transcript of a video from its URL with SocialScrape."""

from __future__ import annotations

from urllib.parse import urlsplit

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.socialscrape.socialscrape_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    SocialScrapeAPIError,
    socialscrape_request,
)


class SocialScrapeTranscriptComponent(Component):
    """Fetch one video's transcript through SocialScrape.

    Works for YouTube, TikTok, Instagram, X, Facebook, LinkedIn, Reddit, Twitch clips,
    Kick clips and Rumble. SocialScrape reads the video on its own servers, so this
    component only sends the URL to ``api.socialscrape.dev``.
    """

    display_name = "SocialScrape Transcript"
    description = "Get the transcript of a video from its URL, on YouTube, TikTok, Instagram, X and more."
    documentation = DOCUMENTATION_URL
    icon = "Share2"
    name = "SocialScrapeTranscript"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="SocialScrape API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="url",
            display_name="Video URL",
            info="The http(s) URL of the video, such as a YouTube watch link or a TikTok video link.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="language",
            display_name="Language",
            info="Language code of the transcript, such as en or es. Leave empty for the video's default.",
            advanced=True,
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for SocialScrape to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Transcript", name="transcript", method="get_transcript"),
    ]

    def get_transcript(self) -> Data:
        """Return the transcript as one ``Data`` with the full text as ``text``."""
        url = str(self.url or "").strip()
        try:
            try:
                parsed = urlsplit(url)
                valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            except ValueError:  # e.g. an unmatched bracket in the host
                valid = False
            if not valid:
                msg = f"Enter an absolute http(s) video URL, such as https://www.youtube.com/watch?v=...; got {url!r}."
                raise SocialScrapeAPIError(msg)
            data = socialscrape_request(
                "/v1/transcript",
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                params={"url": url, "language": str(self.language or "").strip()},
            )
        except SocialScrapeAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        transcript = Data(text=str(data.get("text") or ""), data=data)
        self.status = transcript
        return transcript
