import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.template.field.base import Output

TRANSCRIPT_ENDPOINT = "https://getyoutubetranscript.com/api/v1/transcript"
REQUEST_TIMEOUT_SECONDS = 60
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
ERROR_BODY_EXCERPT_CHARS = 200


def _http_error_message(error: httpx.HTTPStatusError) -> str:
    """Describe a non-2xx API response, keeping the API's own message.

    Errors carry ``{"success": false, "code": ..., "message": ...}``. A non-JSON body
    (for example from a proxy) is kept as a short excerpt so the cause is not lost.
    """
    response = error.response
    detail = None
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get("message") or payload.get("code")
    except ValueError:
        detail = None
    body_excerpt = " ".join(response.text.split())[:ERROR_BODY_EXCERPT_CHARS]
    reason = detail or body_excerpt or response.reason_phrase or "request failed"
    return f"GetYouTubeTranscript API error {response.status_code}: {reason}"


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, SECONDS_PER_HOUR)
    minutes, secs = divmod(remainder, SECONDS_PER_MINUTE)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class GetYouTubeTranscriptComponent(Component):
    """Component for fetching YouTube video transcripts with the GetYouTubeTranscript API."""

    display_name = "GetYouTubeTranscript"
    description = "Get the transcript of a YouTube video with the GetYouTubeTranscript API."
    documentation = "https://getyoutubetranscript.com/docs"
    icon = "GetYouTubeTranscript"

    inputs = [
        MessageTextInput(
            name="video",
            display_name="Video",
            required=True,
            info="YouTube video URL or 11-character video ID.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="getyoutubetranscript_api_key",
            display_name="GetYouTubeTranscript API Key",
            required=True,
            info="Your GetYouTubeTranscript API key. Get one at https://getyoutubetranscript.com.",
            password=True,
        ),
        MessageTextInput(
            name="language",
            display_name="Language",
            required=False,
            advanced=True,
            info="Caption language code, for example 'en' or 'es'. Leave empty for the API default.",
        ),
        BoolInput(
            name="include_timestamps",
            display_name="Include Timestamps",
            value=False,
            advanced=True,
            info="Prefix each caption line with its start time and add a per-line 'segments' list to the Data output.",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.  Keep it specific so an
        # Agent can hold this tool next to other YouTube components.  Only the text
        # output is exposed as a tool; the Data output carries the same call's metadata
        # for non-agent flows.
        Output(display_name="Transcript", name="transcript", method="get_youtube_transcript"),
        Output(display_name="Transcript Data", name="transcript_data", method="get_transcript_data", tool_mode=False),
    ]

    def _fetch(self) -> dict:
        """Call the transcript endpoint and return its ``data`` object."""
        if not self.getyoutubetranscript_api_key:
            msg = "GetYouTubeTranscript API key is required. Set the GetYouTubeTranscript API Key input."
            raise ValueError(msg)
        video = (self.video or "").strip()
        if not video:
            msg = "A YouTube video URL or ID is required."
            raise ValueError(msg)

        params = {"v": video}
        language = (self.language or "").strip()
        if language:
            params["language"] = language
        if self.include_timestamps:
            params["timestamps"] = "true"

        headers = {
            "Authorization": f"Bearer {self.getyoutubetranscript_api_key}",
            "Accept": "application/json",
            # Identify the integration to the API; keeps traffic attributable.
            "User-Agent": "langflow-getyoutubetranscript-bundle",
        }
        response = httpx.get(TRANSCRIPT_ENDPOINT, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            msg = "GetYouTubeTranscript API returned an unexpected response (expected a data object)."
            raise ValueError(msg)  # noqa: TRY004
        return data

    def _pre_run_setup(self) -> None:
        # Langflow calls this before each build; start every build with a fresh request.
        self._fetch_cache = None

    def _request_key(self) -> tuple:
        return (
            (self.video or "").strip(),
            (self.language or "").strip(),
            bool(self.include_timestamps),
            str(self.getyoutubetranscript_api_key or ""),
        )

    def _fetch_or_error(self) -> tuple[dict | None, str | None]:
        """Return ``(data, None)`` on success or ``(None, message)`` so outputs never raise.

        Both outputs share one request for the same inputs, so using both does not spend
        two credits. The result is keyed by the inputs, so tool calls (which copy the
        component) and changed inputs always fetch fresh.
        """
        key = self._request_key()
        cached = getattr(self, "_fetch_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        try:
            result: tuple[dict | None, str | None] = (self._fetch(), None)
        except httpx.HTTPStatusError as e:
            result = (None, _http_error_message(e))
        except (httpx.HTTPError, ValueError) as e:
            result = (None, str(e))
        self._fetch_cache = (key, result)
        return result

    def _transcript_text(self, data: dict) -> str:
        segments = data.get("segments")
        if self.include_timestamps and isinstance(segments, list) and segments:
            return "\n".join(
                f"[{_format_timestamp(segment.get('start') or 0)}] {segment.get('text', '')}"
                for segment in segments
                if isinstance(segment, dict)
            )
        return data.get("transcript") or ""

    def get_youtube_transcript(self) -> Message:
        """Fetch the transcript and return it as a Message."""
        data, error = self._fetch_or_error()
        if error:
            self.status = error
            return Message(text=error)
        message = Message(text=self._transcript_text(data))
        self.status = message
        return message

    def get_transcript_data(self) -> Data:
        """Fetch the transcript and return it with the video metadata as Data."""
        data, error = self._fetch_or_error()
        if error:
            self.status = error
            return Data(text=error, data={"error": error})
        result = Data(text=self._transcript_text(data), data=data)
        self.status = result
        return result
