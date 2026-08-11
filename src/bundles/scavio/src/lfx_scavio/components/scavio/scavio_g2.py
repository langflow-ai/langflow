from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    choice_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Search": Endpoint(
        path="/api/v1/g2/search",
        credits=5,
        fields=("query", "page", "limit", "sort", "rating", "url"),
        result_keys=("products",),
    ),
    "Product Details": Endpoint(
        path="/api/v1/g2/product",
        credits=5,
        fields=("product_id", "url"),
    ),
    "Reviews": Endpoint(
        path="/api/v1/g2/reviews",
        credits=5,
        fields=("product_id", "url", "page", "sort", "rating", "company_size", "role", "region", "query"),
        result_keys=("reviews",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioG2Component(ScavioBaseComponent):
    display_name = "Scavio G2"
    description = (
        "G2 through Scavio: search, product details, reviews (`/api/v1/g2/*`, 5 credits each). Search G2 for B2B "
        "software products: star rating, review count, vendor, categories, seller description, logo; each row carries "
        "product_id and slug. Pagination: page + limit -- `limit` capped at 100 on our side; G2 itself keeps "
        "paginating at any size."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioG2"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "query",
            "Query",
            "Software product or category to search for.",
            tool_mode=True,
        ),
        number_input(
            "page",
            "Page",
            "Result page, 1-based. 20 per page unless limit says otherwise.",
        ),
        number_input(
            "limit",
            "Limit",
            (
                "Products per page, 1-100. Capped at 100 so one request cannot ask for a multi-megabyte page. "
                "Default: 20."
            ),
        ),
        choice_input(
            "sort",
            "Sort",
            "Sort order for the results. Options: relevance, popular, alphabetical, rating. Default: relevance.",
            ["", "relevance", "popular", "alphabetical", "rating"],
            advanced=True,
        ),
        number_input(
            "rating",
            "Rating",
            "Only return products at or above this star rating. Options: 1, 2, 3, 4, 5.",
        ),
        text_input(
            "url",
            "URL",
            "Full g2.com/search URL, usable instead of query.",
        ),
        text_input(
            "product_id",
            "Product ID",
            "G2 slug (notion) or the numeric G2 id (82623) as a string. Both resolve on the same upstream path.",
        ),
        choice_input(
            "company_size",
            "Company Size",
            (
                "Reviewer company size: small_business (<=50), mid_market (51-1000), enterprise (>1000). Options: "
                "small_business, mid_market, enterprise."
            ),
            ["", "small_business", "mid_market", "enterprise"],
            advanced=True,
        ),
        choice_input(
            "role",
            "Role",
            (
                "Reviewer role filter. Options: user, administrator, executive_sponsor, internal_consultant, "
                "consultant, agency, industry_analyst."
            ),
            [
                "",
                "user",
                "administrator",
                "executive_sponsor",
                "internal_consultant",
                "consultant",
                "agency",
                "industry_analyst",
            ],
            advanced=True,
        ),
        choice_input(
            "region",
            "Region",
            "Reviewer region filter. Options: north_america, europe, asia, latin_america, anz, middle_east, africa.",
            ["", "north_america", "europe", "asia", "latin_america", "anz", "middle_east", "africa"],
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
