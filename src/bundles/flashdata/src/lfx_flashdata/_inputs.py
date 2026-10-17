"""Validated tool arguments. Credentials are never part of these schemas."""

import re
from typing import Annotated, Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self

MAX_CLIP_SECONDS = 12 * 60 * 60
SHORT_URL_PARTS = 2
VIDEO_URL_PARTS = 3


Query = Annotated[str, Field(min_length=1, max_length=2000)]
Language = Annotated[str, Field(pattern=r"^[A-Za-z0-9-]{1,35}$")]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True, populate_by_name=True)


class GoogleInput(_Input):
    """Google source parameters; omitted settings use provider behavior."""

    query: Query = Field(description="Search query, between 1 and 2,000 characters.")
    num: int | None = Field(default=None, ge=1, le=100, description="Requested result count.")
    page: int | None = Field(default=None, ge=1, le=100, description="Search result page.")
    autocorrect: bool | None = Field(default=None, description="Enable spelling autocorrection.")
    gl: Annotated[str, Field(pattern=r"^[A-Za-z]{2}$")] | None = Field(
        default=None, description="Two-letter country code, for example us."
    )
    hl: Language | None = Field(default=None, description="Interface language code, for example en.")
    location: Annotated[str, Field(min_length=1, max_length=200)] | None = Field(
        default=None, description="Optional geographic search location."
    )
    tbs: Annotated[str, Field(min_length=1, max_length=200)] | None = Field(
        default=None, description="Optional Google time filter, for example qdr:w."
    )


class YouTubeSearchFilters(_Input):
    """Optional YouTube search filters, including feature flags."""

    duration: Literal["<4", "4-20", ">20"] | None = None
    sort_by: Literal["rating", "relevance", "view_count", "upload_date"] | None = None
    type: Literal["video", "channel", "playlist", "movie"] | None = None
    upload_date: Literal["today", "last_hour", "this_week", "this_month", "this_year"] | None = None
    video_360: bool | None = Field(default=None, alias="360")
    video_3d: bool | None = Field(default=None, alias="3d")
    video_4k: bool | None = Field(default=None, alias="4k")
    creative_commons: bool | None = None
    hd: bool | None = None
    hdr: bool | None = None
    live: bool | None = None
    location: bool | None = None
    purchased: bool | None = None
    subtitles: bool | None = None
    vr180: bool | None = None


class YouTubeSearchInput(_Input):
    """YouTube video search parameters."""

    query: Query = Field(description="YouTube search query, between 1 and 2,000 characters.")
    max_results: int = Field(default=10, ge=1, le=20, description="Requested number of videos.")
    filters: YouTubeSearchFilters | None = None


class YouTubeExtendedSearchInput(YouTubeSearchInput):
    """Larger searches have a separate source and rate; count is not guaranteed."""

    max_results: int = Field(default=20, ge=1, le=700, description="Requested result limit, up to 700.")


class _VideoInput(_Input):
    video_id: str = Field(description="11-character YouTube video ID or a YouTube video URL.")

    @field_validator("video_id")
    @classmethod
    def normalize_video_id(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
            return value
        try:
            url = urlsplit(value)
            parts = url.path.split("/")
            candidate = ""
            if url.scheme in ("http", "https") and not url.username and not url.password:
                if url.hostname == "youtu.be" and (
                    len(parts) == SHORT_URL_PARTS or (len(parts) == SHORT_URL_PARTS + 1 and not parts[2])
                ):
                    candidate = parts[1]
                elif url.hostname in (
                    "youtube.com",
                    "www.youtube.com",
                    "m.youtube.com",
                    "music.youtube.com",
                ):
                    if url.path == "/watch":
                        candidate = parse_qs(url.query).get("v", [""])[0]
                    elif (
                        len(parts) == VIDEO_URL_PARTS or (len(parts) == VIDEO_URL_PARTS + 1 and not parts[3])
                    ) and parts[1] in (
                        "shorts",
                        "embed",
                        "live",
                    ):
                        candidate = parts[2]
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
                return candidate
        except ValueError:
            pass
        msg = "Enter an 11-character YouTube ID or a youtube.com / youtu.be video URL."
        raise ValueError(msg)


class YouTubeMetadataInput(_VideoInput):
    """YouTube metadata parameters."""

    include_chapters: bool = Field(default=True, description="Include available video chapters.")
    include_formats: bool = Field(default=True, description="Include available format metadata.")


class YouTubeTranscriptInput(_VideoInput):
    """YouTube transcript parameters; no implicit language or caption fallback."""

    language: Language = Field(default="en", description="Requested caption language code.")
    auto: bool = Field(
        default=True,
        description="True requests automatic captions; false requests manually authored captions.",
    )


class YouTubeCaptionsInput(YouTubeTranscriptInput):
    """Select uploader captions by default, without fallback."""

    auto: bool = Field(default=False, description="False selects manual; true automatic captions.")


class YouTubeTrainabilityInput(_VideoInput):
    """Inspect license labels; this does not establish training permission."""


class YouTubeChannelInput(_Input):
    handle: Annotated[str, Field(min_length=1, max_length=100)] = Field(
        description="YouTube channel handle, for example @jawed."
    )
    video_limit: int = Field(default=20, ge=1, le=100)


class YouTubeSuggestionsInput(_Input):
    query: Query = Field(description="YouTube search prefix.")
    language: Language = "en"
    region: Annotated[str, Field(pattern=r"^[A-Za-z]{2}$")] = "US"


class YouTubeDownloadInput(_VideoInput):
    """Media options only. Storage credentials are injected by the application."""

    download_type: Literal["audio_video", "video", "audio"] = "audio_video"
    video_quality: (
        Annotated[
            str,
            Field(pattern=r"^(best|worst|(?:<=|==|>=)(?:144|360|480|720|1080|1440|2160|4320))$"),
        ]
        | None
    ) = None
    fps: Annotated[str, Field(pattern=r"^(?:>=|<=|==)(?:[1-9]\d?|1\d\d|2[0-3]\d|240)$")] | None = None
    audio_language: Literal["default", "original"] | None = None
    audio_quality: Literal["best", "320", "256", "192", "128"] | None = None
    yt_dlp_format: Annotated[str, Field(min_length=1, max_length=1024)] | None = None
    upload_metadata: bool = False
    output_format: Literal["mp4", "webm", "mkv", "m4a", "mp3", "opus"] | None = None
    start_at: Annotated[str, Field(pattern=r"^\d{1,2}:[0-5]\d:[0-5]\d$")] | None = None
    end_at: Annotated[str, Field(pattern=r"^\d{1,2}:[0-5]\d:[0-5]\d$")] | None = None

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        audio = self.download_type == "audio"
        formats = ("m4a", "mp3", "opus") if audio else ("mp4", "webm", "mkv")
        if self.output_format is not None and self.output_format not in formats:
            msg = "output_format is incompatible with download_type."
            raise ValueError(msg)
        if self.yt_dlp_format and any(c < " " or c == "\x7f" for c in self.yt_dlp_format):
            msg = "yt_dlp_format must not contain control characters."
            raise ValueError(msg)
        if not self.yt_dlp_format:
            if audio and (self.video_quality is not None or self.fps is not None):
                msg = "video_quality and fps do not apply to audio downloads."
                raise ValueError(msg)
            if self.download_type == "video" and self.audio_language is not None:
                msg = "audio_language does not apply to video-only downloads."
                raise ValueError(msg)
        if not audio and self.audio_quality is not None:
            msg = "audio_quality applies only to audio downloads."
            raise ValueError(msg)
        times = {}
        for field in ("start_at", "end_at"):
            value = getattr(self, field)
            if value is not None:
                h, m, s = map(int, value.split(":"))
                times[field] = h * 3600 + m * 60 + s
                if times[field] > MAX_CLIP_SECONDS:
                    msg = "Clip timestamps must not exceed 12:00:00."
                    raise ValueError(msg)
        if "end_at" in times and times["end_at"] <= times.get("start_at", 0):
            msg = "end_at must be later than start_at."
            raise ValueError(msg)
        return self


class DownloadJobInput(_Input):
    job_id: Annotated[str, Field(pattern=r"^job_[A-Za-z0-9-]{1,100}$")] = Field(
        description="Job ID from a YouTube download submission."
    )
