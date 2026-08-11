from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
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
    "Profile Details": Endpoint(
        path="/api/v1/kuaishou/profile",
        credits=10,
        fields=("target_user_id",),
        required=("target_user_id",),
        wire={"target_user_id": "user_id"},
    ),
    "User Posts": Endpoint(
        path="/api/v1/kuaishou/user/posts",
        credits=1,
        fields=("target_user_id", "cursor"),
        required=("target_user_id",),
        wire={"target_user_id": "user_id"},
    ),
    "User Live": Endpoint(
        path="/api/v1/kuaishou/user/live",
        credits=1,
        fields=("target_user_id",),
        required=("target_user_id",),
        wire={"target_user_id": "user_id"},
    ),
    "Resolve Share Link": Endpoint(
        path="/api/v1/kuaishou/user/resolve",
        credits=1,
        fields=("share_link",),
        required=("share_link",),
    ),
    "Video Details": Endpoint(
        path="/api/v1/kuaishou/video",
        credits=2,
        fields=("photo_id", "url"),
    ),
    "Video Comments": Endpoint(
        path="/api/v1/kuaishou/video/comments",
        credits=1,
        fields=("photo_id", "cursor"),
        required=("photo_id",),
    ),
    "Comment Replies": Endpoint(
        path="/api/v1/kuaishou/video/sub-comments",
        credits=1,
        fields=("photo_id", "root_comment_id", "cursor", "count"),
        required=("photo_id", "root_comment_id"),
    ),
    "Videos In Batch": Endpoint(
        path="/api/v1/kuaishou/videos/batch",
        credits=40,
        fields=("photo_ids",),
        required=("photo_ids",),
        csv_fields=("photo_ids",),
    ),
    "Search": Endpoint(
        path="/api/v1/kuaishou/search",
        credits=10,
        fields=("keyword", "cursor"),
        required=("keyword",),
        result_keys=("mixFeeds",),
    ),
    "Search Videos": Endpoint(
        path="/api/v1/kuaishou/search/videos",
        credits=10,
        fields=("keyword", "cursor"),
        required=("keyword",),
        result_keys=("mixFeeds",),
    ),
    "Search Users": Endpoint(
        path="/api/v1/kuaishou/search/users",
        credits=10,
        fields=("keyword", "cursor"),
        required=("keyword",),
        result_keys=("mixFeeds",),
    ),
    "Search Live": Endpoint(
        path="/api/v1/kuaishou/search/live",
        credits=10,
        fields=("keyword", "cursor"),
        required=("keyword",),
        result_keys=("mixFeeds",),
    ),
    "Tag Feed": Endpoint(
        path="/api/v1/kuaishou/tag/feed",
        credits=1,
        fields=("tag", "cursor"),
        required=("tag",),
        result_keys=("mixFeeds",),
    ),
    "Trending": Endpoint(
        path="/api/v1/kuaishou/trending",
        credits=1,
        fields=("board",),
        result_keys=("hots",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioKuaishouComponent(ScavioBaseComponent):
    display_name = "Scavio Kuaishou"
    description = (
        "Kuaishou through Scavio: profile details, user posts, user live, resolve share link, video details, video "
        "comments, comment replies, videos in batch, search, search videos, search users, search live, tag feed, "
        "trending (`/api/v1/kuaishou/*`, 1-40 credits depending on the endpoint). Profile details for a Kuaishou "
        "user."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioKuaishou"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Profile Details"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Profile Details"),
        text_input(
            "target_user_id",
            "User ID",
            "Kuaishou user id.",
        ),
        cursor_input(
            (
                "Pagination cursor taken from a previous response's next_cursor. Keep the other arguments identical "
                "across paginated calls."
            ),
        ),
        text_input(
            "share_link",
            "Share Link",
            (
                "A kuaishou.com or v.kuaishou.com share link. kwai.com links are NOT supported -- TikHub does not "
                "serve Kwai international."
            ),
        ),
        text_input(
            "photo_id",
            "Photo ID",
            "Kuaishou photo (video) id.",
        ),
        text_input(
            "url",
            "URL",
            "A kuaishou.com video URL, usable instead of photo_id.",
            tool_mode=True,
        ),
        text_input(
            "root_comment_id",
            "Root Comment ID",
            "Id of the root comment whose replies you want.",
        ),
        number_input(
            "count",
            "Count",
            "Replies to return in this page, 1-50.",
        ),
        text_input(
            "photo_ids",
            "Photo Ids",
            "Kuaishou photo ids to fetch in one call. Hard cap of 20 ids.",
        ),
        text_input(
            "keyword",
            "Keyword",
            "Search keyword.",
        ),
        text_input(
            "tag",
            "Tag",
            "Hashtag to read the feed for, without the leading #.",
        ),
        choice_input(
            "board",
            "Board",
            "Which leaderboard to return. Options: hot, live, shopping, brand, music. Default: hot.",
            ["", "hot", "live", "shopping", "brand", "music"],
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
