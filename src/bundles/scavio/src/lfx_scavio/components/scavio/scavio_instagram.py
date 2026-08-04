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

# Instagram credits are per endpoint, never a flat rate: 10 for the hedged V3
# endpoints, 8 for the two with no fallback leg, 2 for the V2-primary feed.
ENDPOINTS = {
    "User Profile": Endpoint(
        path="/api/v1/instagram/profile",
        credits=10,
        fields=("username", "user_id"),
    ),
    "User Posts": Endpoint(
        path="/api/v1/instagram/user/posts",
        credits=2,
        fields=("username", "user_id", "count", "cursor"),
        result_keys=("items", "data"),
    ),
    "User Reels": Endpoint(
        path="/api/v1/instagram/user/reels",
        credits=10,
        fields=("username", "user_id", "count", "cursor"),
        result_keys=("items", "data"),
    ),
    "User Tagged": Endpoint(
        path="/api/v1/instagram/user/tagged",
        credits=10,
        fields=("username", "user_id", "count", "cursor"),
        result_keys=("items",),
    ),
    "User Stories": Endpoint(
        path="/api/v1/instagram/user/stories",
        credits=10,
        fields=("username", "user_id"),
        result_keys=("items",),
    ),
    "User Followers": Endpoint(
        path="/api/v1/instagram/user/followers",
        credits=10,
        fields=("username", "user_id", "count", "cursor"),
        result_keys=("users",),
    ),
    "User Followings": Endpoint(
        path="/api/v1/instagram/user/followings",
        credits=10,
        fields=("username", "user_id", "count", "cursor"),
        result_keys=("users",),
    ),
    "Post Details": Endpoint(
        path="/api/v1/instagram/post",
        credits=8,
        fields=("url", "media_id", "shortcode"),
        result_keys=("items",),
    ),
    "Post Comments": Endpoint(
        path="/api/v1/instagram/post/comments",
        credits=10,
        fields=("shortcode", "url", "cursor", "sort_order"),
        result_keys=("comments",),
    ),
    "Comment Replies": Endpoint(
        path="/api/v1/instagram/post/comments/replies",
        credits=8,
        fields=("media_id", "comment_id", "cursor"),
        required=("media_id", "comment_id"),
        result_keys=("child_comments",),
    ),
    "Search Users": Endpoint(
        path="/api/v1/instagram/search/users",
        credits=10,
        fields=("keyword", "cursor"),
        required=("keyword",),
        result_keys=("users", "items"),
    ),
    "Search Hashtags": Endpoint(
        path="/api/v1/instagram/search/hashtags",
        credits=10,
        fields=("keyword", "cursor"),
        required=("keyword",),
        result_keys=("hashtags", "items"),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioInstagramComponent(ScavioAPIMixin, Component):
    display_name = "Scavio Instagram"
    description = (
        "The full Scavio Instagram surface: profiles, posts, reels, tagged posts, stories, followers and "
        "followings, post detail, comments and replies, and user and hashtag search. Credits are per "
        "endpoint - 10 for the hedged endpoints, 8 for post and comment replies, 2 for user posts."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioInstagram"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "User Profile"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "User Profile"),
        text_input("username", "Username", "Instagram handle without the @.", tool_mode=True),
        text_input("user_id", "User ID", "Numeric Instagram user id as a string. Takes precedence over Username."),
        text_input("keyword", "Keyword", "Search term. Instagram search takes keyword, not query.", tool_mode=True),
        text_input(
            "shortcode",
            "Shortcode",
            "Post shortcode, e.g. DUajw4YkorV. Accepted by Post Details and Post Comments.",
            tool_mode=True,
        ),
        text_input("url", "Post URL", "Full post URL. Accepted by Post Details and Post Comments."),
        text_input(
            "media_id",
            "Media ID",
            "Numeric media id. Post Details accepts it, and Comment Replies requires it - resolve it "
            "through Post Details first, because Post Comments does not return one.",
        ),
        text_input("comment_id", "Comment ID", "Numeric comment id to fetch replies for."),
        cursor_input("Pagination cursor echoed from a previous response."),
        number_input(
            "count",
            "Count",
            "Items per page. Feeds cap at 50, follow lists at 100. Defaults to 12 when left at 0.",
            value=12,
        ),
        choice_input(
            "sort_order",
            "Comment Sort",
            "Comment ordering. Empty keeps the API default of popular.",
            ["", "popular", "newest"],
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
