from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    cursor_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    text_input,
)

ENDPOINTS = {
    "Profile Details": Endpoint(
        path="/api/v1/threads/profile",
        credits=2,
        fields=("username", "target_user_id"),
        wire={"target_user_id": "user_id"},
        credit_note=(
            "Costs 2 credits when addressed by user_id and 4 credits when addressed by username -- the handle needs "
            "a second upstream lookup, so prefer user_id."
        ),
    ),
    "User Posts": Endpoint(
        path="/api/v1/threads/user/posts",
        credits=2,
        fields=("username", "target_user_id", "cursor"),
        result_keys=("posts",),
        wire={"target_user_id": "user_id"},
        credit_note="Costs 2 credits when addressed by user_id and 4 credits when addressed by username.",
    ),
    "User Replies": Endpoint(
        path="/api/v1/threads/user/replies",
        credits=2,
        fields=("username", "target_user_id", "cursor"),
        result_keys=("posts",),
        wire={"target_user_id": "user_id"},
        credit_note="Costs 2 credits when addressed by user_id and 4 credits when addressed by username.",
    ),
    "Post Details": Endpoint(
        path="/api/v1/threads/post",
        credits=2,
        fields=("post_id", "url"),
    ),
    "Post Comments": Endpoint(
        path="/api/v1/threads/post/comments",
        credits=2,
        fields=("post_id", "cursor"),
        required=("post_id",),
        result_keys=("comments",),
    ),
    "User Search": Endpoint(
        path="/api/v1/threads/search/users",
        credits=2,
        fields=("query",),
        required=("query",),
        result_keys=("users",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioThreadsComponent(ScavioBaseComponent):
    display_name = "Scavio Threads"
    description = (
        "Threads through Scavio: profile details, user posts, user replies, post details, post comments, user search "
        "(`/api/v1/threads/*`; credit cost depends on the request body - see each endpoint). Profile details for a "
        "Threads user, by user_id (2cr) or username (4cr)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioThreads"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Profile Details"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Profile Details"),
        text_input(
            "username",
            "Username",
            (
                "Threads handle without the @. Costs 2 extra credits because the handle has to be resolved with a "
                "second upstream call -- prefer user_id."
            ),
        ),
        text_input(
            "target_user_id",
            "User ID",
            "Numeric Threads user id, e.g. 63625256886. This is the cheap path.",
        ),
        cursor_input(
            (
                "Pagination cursor taken from a previous response's next_cursor. Keep the other arguments identical "
                "across paginated calls."
            ),
        ),
        text_input(
            "post_id",
            "Post ID",
            "Threads post id.",
        ),
        text_input(
            "url",
            "URL",
            "A threads.net post URL, usable instead of post_id.",
            tool_mode=True,
        ),
        text_input(
            "query",
            "Query",
            "Name or handle to look for.",
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
