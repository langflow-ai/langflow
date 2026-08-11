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

ENDPOINTS = {
    "Search": Endpoint(
        path="/api/v1/meta-ads/search",
        credits=1,
        fields=("query", "country", "active_status", "ad_type", "media_type", "search_type", "cursor"),
        required=("query",),
        result_keys=("ads",),
    ),
    "Advertiser": Endpoint(
        path="/api/v1/meta-ads/advertiser",
        credits=1,
        fields=("page_id", "country", "active_status", "ad_type", "media_type", "cursor"),
        required=("page_id",),
        result_keys=("ads",),
    ),
    "Ad Details": Endpoint(
        path="/api/v1/meta-ads/ad",
        credits=1,
        fields=("ad_archive_id",),
        required=("ad_archive_id",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioMetaAdsComponent(ScavioBaseComponent):
    display_name = "Scavio Meta Ad Library"
    description = (
        "Meta Ad Library through Scavio: search, advertiser, ad details (`/api/v1/meta-ads/*`, 1 credit each). Search "
        "the Meta Ad Library: 30 ads on page 1 with full creative (page name, ad copy, headline, CTA, images and "
        "videos, platforms, run dates), then cursor-paginated. Pagination: cursor -> next_cursor. Page 1 is 30 ads, "
        "then 10 per page; walk has_next_page to read a whole query."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioMetaAds"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "query",
            "Query",
            "Keyword, brand or advertiser name to search the library for.",
            tool_mode=True,
        ),
        text_input(
            "country",
            "Country",
            "Two-letter country code for the ad library storefront. Default: US.",
        ),
        choice_input(
            "active_status",
            "Active Status",
            "Whether to return running, stopped or all ads. Options: all, active, inactive. Default: all.",
            ["", "all", "active", "inactive"],
            advanced=True,
        ),
        choice_input(
            "ad_type",
            "Ad Type",
            (
                "Set to political_and_issue_ads to expose spend, reach, impressions and the paid-for-by disclosure. "
                "Commercial ads leave those null. Options: all, political_and_issue_ads. Default: all."
            ),
            ["", "all", "political_and_issue_ads"],
            advanced=True,
        ),
        choice_input(
            "media_type",
            "Media Type",
            "Creative media type filter. Options: all, image, video, meme, image_and_meme, none.",
            ["", "all", "image", "video", "meme", "image_and_meme", "none"],
            advanced=True,
        ),
        choice_input(
            "search_type",
            "Search Type",
            (
                "Whether the query is matched as an exact phrase. Options: keyword_unordered, keyword_exact_phrase. "
                "Default: keyword_unordered."
            ),
            ["", "keyword_unordered", "keyword_exact_phrase"],
            advanced=True,
        ),
        cursor_input(
            (
                "next_cursor from the previous response. Page 1 is 30 ads, then 10 per page. ALL OTHER FILTERS ARE "
                "IGNORED when a cursor is present -- the cursor already carries them."
            ),
        ),
        text_input(
            "page_id",
            "Page ID",
            "The advertiser's numeric Facebook Page id.",
        ),
        text_input(
            "ad_archive_id",
            "Ad Archive ID",
            "The ad's numeric archive id.",
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
