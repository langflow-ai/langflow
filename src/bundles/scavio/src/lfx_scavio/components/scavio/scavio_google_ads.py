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
    "Search": Endpoint(
        path="/api/v1/googleads/search",
        credits=1,
        fields=("domain", "advertiser_id", "region", "format", "platform", "topic", "limit", "cursor"),
        result_keys=("creatives",),
    ),
    "Advertiser Lookup": Endpoint(
        path="/api/v1/googleads/advertisers",
        credits=1,
        fields=("query", "region", "limit"),
        required=("query",),
        result_keys=("suggestions",),
    ),
    "Creative Details": Endpoint(
        path="/api/v1/googleads/creative",
        credits=1,
        fields=("advertiser_id", "creative_id"),
        required=("advertiser_id", "creative_id"),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioGoogleAdsComponent(ScavioBaseComponent):
    display_name = "Scavio Google Ads"
    description = (
        "Google Ads through Scavio: search, advertiser lookup, creative details (`/api/v1/googleads/*`, 1 credit "
        "each). Every ad Google is running for one advertiser: the creative, advertiser id and name, format, "
        "first/last seen dates, days actually run, plus total_ads_min/total_ads_max. Pagination: cursor -> "
        "next_cursor, 100 creatives per page. Re-send the SAME filters alongside the cursor."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioGoogleAds"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "domain",
            "Domain",
            (
                "Advertiser website: bare host, www host or full URL, reduced to the registrable host. This is the "
                "ONLY way to get the `domain` field back on each row."
            ),
            tool_mode=True,
        ),
        text_input(
            "advertiser_id",
            "Advertiser ID",
            (
                "Google advertiser id, e.g. AR16735076323512287233. The shape is checked before any request, so a "
                "typo costs nothing."
            ),
        ),
        text_input(
            "region",
            "Region",
            (
                "ISO alpha-2 country (US, GB, DE) or a Google geo criteria id as a string. It also scopes the deep "
                "links on every row. Default: worldwide."
            ),
        ),
        choice_input(
            "format",
            "Format",
            (
                "Creative format. The three sets are DISJOINT -- an advertiser's text, image and video ads share no "
                "creatives. Default: all formats. Options: text, image, video."
            ),
            ["", "text", "image", "video"],
            advanced=True,
        ),
        choice_input(
            "platform",
            "Platform",
            "Surface the ad ran on. Default: all surfaces. Options: play, maps, search, shopping, youtube.",
            ["", "play", "maps", "search", "shopping", "youtube"],
            advanced=True,
        ),
        choice_input(
            "topic",
            "Topic",
            "Ad topic filter. Options: all, political. Default: all.",
            ["", "all", "political"],
            advanced=True,
        ),
        number_input(
            "limit",
            "Limit",
            (
                "Creatives per page, 1-100. 100 is a HARD UPSTREAM CEILING, not our policy: Google answers a larger "
                "request with ZERO rows rather than an error. Default: 40."
            ),
        ),
        cursor_input(
            (
                "next_cursor from the previous response. Re-send the SAME filters alongside it. Null once the "
                "result set is exhausted."
            ),
        ),
        text_input(
            "query",
            "Query",
            "Advertiser name or domain to resolve.",
        ),
        text_input(
            "creative_id",
            "Creative ID",
            (
                "Creative id. It must belong to the advertiser_id sent with it -- the lookup is keyed by the pair "
                "and a mismatch is a 404."
            ),
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
