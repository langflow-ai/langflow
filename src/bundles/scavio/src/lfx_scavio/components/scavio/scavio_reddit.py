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
    text_input,
)

# Reddit search takes query and cursor and nothing else: the backend strips any
# type or sort key it is sent, so exposing one would be a dead control.
ENDPOINTS = {
    "Search": Endpoint(
        path="/api/v1/reddit/search",
        credits=1,
        fields=("query", "cursor"),
        required=("query",),
        result_keys=("results",),
    ),
    "Search Suggestions": Endpoint(
        path="/api/v1/reddit/search/suggestions",
        credits=1,
        fields=("query",),
        required=("query",),
        result_keys=("suggestions",),
    ),
    "Post Details": Endpoint(
        path="/api/v1/reddit/post",
        credits=1,
        fields=("post_id", "url"),
    ),
    "Post Comments": Endpoint(
        path="/api/v1/reddit/post/comments",
        credits=1,
        fields=("post_id", "sort", "cursor"),
        required=("post_id",),
        result_keys=("comments",),
    ),
    "Comment Replies": Endpoint(
        path="/api/v1/reddit/post/comments/replies",
        credits=1,
        fields=("post_id", "cursor", "sort"),
        required=("post_id", "cursor"),
        result_keys=("replies",),
    ),
    "Subreddit Details": Endpoint(
        path="/api/v1/reddit/subreddit",
        credits=1,
        fields=("subreddit",),
        required=("subreddit",),
    ),
    "Subreddit Posts": Endpoint(
        path="/api/v1/reddit/subreddit/posts",
        credits=1,
        fields=("subreddit", "feed_sort", "cursor"),
        required=("subreddit",),
        result_keys=("posts",),
        wire={"feed_sort": "sort"},
    ),
    "User Profile": Endpoint(
        path="/api/v1/reddit/user",
        credits=1,
        fields=("username",),
        required=("username",),
    ),
    "User Posts": Endpoint(
        path="/api/v1/reddit/user/posts",
        credits=1,
        fields=("username", "sort", "cursor"),
        required=("username",),
        result_keys=("posts",),
    ),
    "User Comments": Endpoint(
        path="/api/v1/reddit/user/comments",
        credits=1,
        fields=("username", "sort", "cursor"),
        required=("username",),
        result_keys=("comments",),
    ),
    "Popular": Endpoint(
        path="/api/v1/reddit/popular",
        credits=1,
        fields=("cursor",),
        result_keys=("posts",),
    ),
    "Trending": Endpoint(
        path="/api/v1/reddit/trending",
        credits=1,
        result_keys=("trending",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioRedditComponent(ScavioBaseComponent):
    display_name = "Scavio Reddit"
    description = (
        "The full Scavio Reddit surface: search, suggestions, post details, comments and replies, "
        "subreddit profile and feed, user profile, posts and comments, plus the popular and trending "
        "boards (`/api/v1/reddit/*`, 1 credit each)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioReddit"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input("query", "Query", "What to search Reddit for.", tool_mode=True),
        text_input(
            "post_id",
            "Post ID",
            "A t3_ fullname, a bare base-36 id, or a post URL. Post Details returns the post on its own - "
            "call Post Comments for the thread.",
            tool_mode=True,
        ),
        text_input("url", "Post URL", "Full Reddit post URL, an alternative to Post ID on Post Details."),
        text_input("subreddit", "Subreddit", "Bare subreddit name, e.g. AskReddit.", tool_mode=True),
        text_input("username", "Username", "Bare Reddit handle, e.g. spez.", tool_mode=True),
        cursor_input(
            "Pagination cursor. Comment Replies requires a reply_cursor taken from a comment in Post Comments."
        ),
        choice_input(
            "sort",
            "Sort",
            "Ordering. Empty keeps the API default, which is TOP for comments and NEW for user feeds.",
            ["", "HOT", "NEW", "TOP", "BEST", "CONTROVERSIAL"],
            advanced=True,
        ),
        choice_input(
            "feed_sort",
            "Feed Sort",
            "Subreddit feed ordering. This is the only endpoint that accepts RISING. Sent as sort.",
            ["", "BEST", "HOT", "NEW", "TOP", "CONTROVERSIAL", "RISING"],
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
