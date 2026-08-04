from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MultiselectInput
from lfx.template.field.base import Output

from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    ScavioAPIMixin,
    api_key_input,
    choice_input,
    cursor_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    text_input,
)

# /api/v1/youtube/metadata is a deprecated alias of /api/v1/youtube/video and is
# deliberately not offered here - "Video Details" targets /video directly.
ENDPOINTS = {
    "Search": Endpoint(
        path="/api/v1/youtube/search",
        credits=2,
        fields=("search", "upload_date", "type", "duration", "sort_by", "features", "cursor"),
        required=("search",),
        result_keys=("results",),
    ),
    "Shorts Search": Endpoint(
        path="/api/v1/youtube/shorts",
        credits=2,
        fields=("search", "sort_by", "cursor"),
        required=("search",),
        result_keys=("results",),
    ),
    "Search Suggestions": Endpoint(
        path="/api/v1/youtube/suggestions",
        credits=1,
        fields=("search", "language", "region"),
        required=("search",),
        result_keys=("suggestions",),
    ),
    "Video Details": Endpoint(
        path="/api/v1/youtube/video",
        credits=1,
        fields=("video_id",),
        required=("video_id",),
    ),
    "Video Comments": Endpoint(
        path="/api/v1/youtube/comments",
        credits=1,
        fields=("video_id", "cursor"),
        required=("video_id",),
        result_keys=("comments",),
    ),
    "Comment Replies": Endpoint(
        path="/api/v1/youtube/comments/replies",
        credits=1,
        fields=("video_id", "reply_cursor", "cursor"),
        required=("video_id", "reply_cursor"),
        result_keys=("replies",),
    ),
    "Transcript": Endpoint(
        path="/api/v1/youtube/transcript",
        credits=8,
        fields=("video_id", "language", "format"),
        required=("video_id",),
    ),
    "Related Videos": Endpoint(
        path="/api/v1/youtube/related",
        credits=1,
        fields=("video_id", "cursor"),
        required=("video_id",),
        result_keys=("results",),
    ),
    "Video Streams": Endpoint(
        path="/api/v1/youtube/streams",
        credits=3,
        fields=("video_id",),
        required=("video_id",),
        result_keys=("formats",),
    ),
    "Channel Search": Endpoint(
        path="/api/v1/youtube/channel/search",
        credits=1,
        fields=("search", "cursor"),
        required=("search",),
        result_keys=("results",),
    ),
    "Channel Details": Endpoint(
        path="/api/v1/youtube/channel",
        credits=1,
        fields=("channel_id",),
        required=("channel_id",),
    ),
    "Channel Videos": Endpoint(
        path="/api/v1/youtube/channel/videos",
        credits=1,
        fields=("channel_id", "cursor"),
        required=("channel_id",),
        result_keys=("results",),
    ),
    "Channel Shorts": Endpoint(
        path="/api/v1/youtube/channel/shorts",
        credits=1,
        fields=("channel_id", "cursor"),
        required=("channel_id",),
        result_keys=("results",),
    ),
    "Channel Community": Endpoint(
        path="/api/v1/youtube/channel/community",
        credits=1,
        fields=("channel_id", "cursor"),
        required=("channel_id",),
        result_keys=("posts",),
    ),
    "Channel Resolve": Endpoint(
        path="/api/v1/youtube/channel/resolve",
        credits=1,
        fields=("channel",),
        required=("channel",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioYouTubeComponent(ScavioAPIMixin, Component):
    display_name = "Scavio YouTube"
    description = (
        "The full Scavio YouTube surface: search, shorts, suggestions, video details, comments, replies, "
        "transcripts, related videos, stream URLs and the five channel endpoints. Costs vary per endpoint "
        "(search and shorts 2, streams 3, transcript 8, everything else 1)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioYouTube"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "search",
            "Search",
            "The query. YouTube's wire field is literally named search, not query.",
            tool_mode=True,
        ),
        text_input(
            "video_id",
            "Video ID or URL",
            "A bare 11-character video id or any watch, shorts, embed or youtu.be URL.",
            tool_mode=True,
        ),
        text_input(
            "channel_id",
            "Channel ID, Handle or URL",
            "A UC... channel id, an @handle, a bare name or a channel URL.",
            tool_mode=True,
        ),
        text_input(
            "channel",
            "Channel to Resolve",
            "A channel @handle or URL to resolve to an id. Channel Resolve is the one endpoint whose field "
            "is named channel rather than channel_id.",
            tool_mode=True,
        ),
        text_input(
            "reply_cursor",
            "Reply Cursor",
            "reply_cursor taken from a comment returned by Video Comments. Comment Replies cannot run "
            "from a video id alone.",
        ),
        cursor_input("Pagination cursor. Echo next_cursor from a previous response."),
        choice_input(
            "upload_date",
            "Upload Date",
            "Restrict search results to a recent upload window.",
            ["", "last_hour", "today", "this_week", "this_month", "this_year"],
            advanced=True,
        ),
        choice_input(
            "type",
            "Result Type",
            "Restrict search results to one kind of result.",
            ["", "video", "channel", "playlist", "movie"],
            advanced=True,
        ),
        choice_input(
            "duration",
            "Duration",
            "Restrict search results by video length.",
            ["", "short", "medium", "long"],
            advanced=True,
        ),
        choice_input(
            "sort_by",
            "Sort By",
            "Ordering for Search and Shorts Search.",
            ["", "relevance", "date", "view_count", "rating"],
            advanced=True,
        ),
        MultiselectInput(
            name="features",
            display_name="Features",
            info="Feature filters applied to Search.",
            options=["hd", "4k", "subtitles", "creative_commons", "live", "360", "3d", "hdr", "vr180"],
            value=[],
            advanced=True,
            dynamic=True,
            show=False,
        ),
        text_input(
            "language", "Language", "Language code, e.g. en. Used by Suggestions and Transcript.", advanced=True
        ),
        text_input("region", "Region", "Region code for Suggestions, e.g. US.", advanced=True),
        choice_input(
            "format",
            "Transcript Format",
            "text returns plain text, srt returns timed captions. Empty means plain text.",
            ["", "text", "srt"],
            advanced=True,
        ),
        max_results_input(),
    ]

    # The endpoint dropdown's default decides what is visible before the user
    # touches anything; update_build_config takes over from there.
    default_visibility(inputs, ENDPOINTS, DEFAULT_ENDPOINT)

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]
