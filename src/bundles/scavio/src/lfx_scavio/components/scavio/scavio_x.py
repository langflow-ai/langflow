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
    text_input,
)

ENDPOINTS = {
    "Search": Endpoint(
        path="/api/v1/x/search",
        credits=1,
        fields=("search", "search_type", "cursor"),
        required=("search",),
        result_keys=("timeline",),
    ),
    "Tweet Details": Endpoint(
        path="/api/v1/x/tweet",
        credits=1,
        fields=("tweet_id",),
        required=("tweet_id",),
    ),
    "Tweet Comments": Endpoint(
        path="/api/v1/x/tweet/comments",
        credits=1,
        fields=("tweet_id", "rank", "cursor"),
        required=("tweet_id",),
        result_keys=("timeline",),
    ),
    "Tweet Retweeters": Endpoint(
        path="/api/v1/x/tweet/retweeters",
        credits=1,
        fields=("tweet_id", "cursor"),
        required=("tweet_id",),
        result_keys=("retweeters",),
    ),
    "User Profile": Endpoint(
        path="/api/v1/x/user",
        credits=1,
        fields=("screen_name",),
        required=("screen_name",),
    ),
    "User Tweets": Endpoint(
        path="/api/v1/x/user/tweets",
        credits=1,
        fields=("screen_name", "cursor"),
        required=("screen_name",),
        result_keys=("timeline",),
    ),
    "User Replies": Endpoint(
        path="/api/v1/x/user/replies",
        credits=1,
        fields=("screen_name", "cursor"),
        required=("screen_name",),
        result_keys=("timeline",),
    ),
    "User Media": Endpoint(
        path="/api/v1/x/user/media",
        credits=1,
        fields=("screen_name", "cursor"),
        required=("screen_name",),
        result_keys=("timeline",),
    ),
    "User Followers": Endpoint(
        path="/api/v1/x/user/followers",
        credits=1,
        fields=("screen_name", "cursor"),
        required=("screen_name",),
        result_keys=("followers",),
    ),
    "User Followings": Endpoint(
        path="/api/v1/x/user/followings",
        credits=1,
        fields=("screen_name", "cursor"),
        required=("screen_name",),
        # The response array is `following`, not `followings`.
        result_keys=("following",),
    ),
    "Trending": Endpoint(
        path="/api/v1/x/trending",
        credits=1,
        fields=("country",),
        result_keys=("trends",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioXComponent(ScavioAPIMixin, Component):
    display_name = "Scavio X"
    description = (
        "The full Scavio X (Twitter) surface: search, tweet detail, comments and retweeters, user profile, "
        "tweets, replies and media, followers and followings, and the trending board "
        "(`/api/v1/x/*`, 1 credit each)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioX"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "search",
            "Search",
            "The query. X search's wire field is literally named search, not query.",
            tool_mode=True,
        ),
        text_input("tweet_id", "Tweet ID", "Numeric tweet id as a string.", tool_mode=True),
        text_input("screen_name", "Screen Name", "X handle without the @, e.g. elonmusk.", tool_mode=True),
        text_input(
            "country",
            "Country",
            "Trending board country as a NAME, not an ISO code, e.g. UnitedStates. Defaults to UnitedStates.",
            tool_mode=True,
        ),
        cursor_input("Pagination cursor echoed from a previous response."),
        choice_input(
            "search_type",
            "Search Type",
            "Search tab. Values are capitalized. Empty keeps the API default of Top.",
            ["", "Top", "Latest", "People", "Photos", "Videos"],
            advanced=True,
        ),
        choice_input(
            "rank",
            "Comment Rank",
            "Comment ordering. Lowercase here, unlike Search Type. Empty keeps the API default of top.",
            ["", "top", "latest"],
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
