from lfx.custom.custom_component.component import Component
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
    number_input,
    text_input,
)

ENDPOINTS = {
    "User Profile": Endpoint(
        path="/api/v1/tiktok/profile",
        credits=1,
        fields=("username", "sec_user_id"),
        result_keys=("user",),
    ),
    "User Posts": Endpoint(
        path="/api/v1/tiktok/user/posts",
        credits=1,
        fields=("sec_user_id", "cursor", "count", "sort_type"),
        required=("sec_user_id",),
        result_keys=("aweme_list",),
    ),
    "User Followers": Endpoint(
        path="/api/v1/tiktok/user/followers",
        credits=1,
        fields=("sec_user_id", "count", "page_token", "min_time"),
        required=("sec_user_id",),
        result_keys=("followers",),
    ),
    "User Followings": Endpoint(
        path="/api/v1/tiktok/user/followings",
        credits=1,
        fields=("sec_user_id", "count", "page_token", "min_time"),
        required=("sec_user_id",),
        result_keys=("followings",),
    ),
    "Video Detail": Endpoint(
        path="/api/v1/tiktok/video",
        credits=1,
        fields=("video_id",),
        required=("video_id",),
        result_keys=("aweme_detail",),
    ),
    "Video Comments": Endpoint(
        path="/api/v1/tiktok/video/comments",
        credits=1,
        fields=("video_id", "cursor", "count"),
        required=("video_id",),
        result_keys=("comments",),
    ),
    "Comment Replies": Endpoint(
        path="/api/v1/tiktok/video/comments/replies",
        credits=1,
        fields=("video_id", "comment_id", "cursor", "count"),
        required=("video_id", "comment_id"),
        result_keys=("comments",),
    ),
    "Search Videos": Endpoint(
        path="/api/v1/tiktok/search/videos",
        credits=1,
        fields=("keyword", "cursor", "count", "sort_type", "publish_time"),
        required=("keyword",),
        result_keys=("aweme_list",),
    ),
    "Search Users": Endpoint(
        path="/api/v1/tiktok/search/users",
        credits=1,
        fields=("keyword", "cursor", "count"),
        required=("keyword",),
        result_keys=("user_list",),
    ),
    "Hashtag Info": Endpoint(
        path="/api/v1/tiktok/hashtag",
        credits=1,
        fields=("hashtag_name", "hashtag_id"),
        result_keys=("challengeInfo",),
    ),
    "Hashtag Videos": Endpoint(
        path="/api/v1/tiktok/hashtag/videos",
        credits=1,
        fields=("hashtag_id", "cursor", "count"),
        required=("hashtag_id",),
        result_keys=("aweme_list",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioTikTokComponent(ScavioAPIMixin, Component):
    display_name = "Scavio TikTok"
    description = (
        "The full Scavio TikTok surface: profiles, user posts, followers and followings, video detail, "
        "comments and replies, video and user search, and hashtag lookups (`/api/v1/tiktok/*`, 1 credit "
        "each). Identity is sec_user_id everywhere except the profile endpoint - resolve it there first."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioTikTok"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "User Profile"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "User Profile"),
        text_input(
            "username",
            "Username",
            "TikTok handle without the @. Accepted on User Profile only.",
            tool_mode=True,
        ),
        text_input(
            "sec_user_id",
            "Sec User ID",
            "TikTok sec_user_id. Required by user posts, followers and followings - read it off a "
            "User Profile response first.",
            tool_mode=True,
        ),
        text_input("video_id", "Video ID", "Numeric TikTok video id.", tool_mode=True),
        text_input("comment_id", "Comment ID", "Numeric comment id to fetch replies for."),
        text_input("keyword", "Keyword", "Search term. TikTok's wire field is keyword, not query.", tool_mode=True),
        text_input("hashtag_name", "Hashtag Name", "Hashtag without the leading #, e.g. fyp.", tool_mode=True),
        text_input(
            "hashtag_id",
            "Hashtag ID",
            "Numeric hashtag id. Hashtag Videos accepts only this - get it from Hashtag Info.",
        ),
        cursor_input('Pagination cursor as a STRING, e.g. "0". Sending a number is rejected.'),
        number_input(
            "count",
            "Count",
            "Items per page. Caps differ per endpoint: 30 feeds, 50 comments, 20 follow lists.",
            value=20,
        ),
        text_input("page_token", "Page Token", "Follow-list pagination token from a previous response.", advanced=True),
        number_input("min_time", "Min Time", "Follow-list pagination timestamp from a previous response."),
        choice_input(
            "sort_type",
            "Sort Type",
            "0 relevance or latest, 1 most liked or popular. Digit strings, not numbers.",
            ["", "0", "1"],
            advanced=True,
        ),
        choice_input(
            "publish_time",
            "Publish Time",
            "Video age filter in days: 0 all time, 1, 7, 30, 90 or 180.",
            ["", "0", "1", "7", "30", "90", "180"],
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
