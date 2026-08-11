from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Search": Endpoint(
        path="/api/v1/capterra/search",
        credits=2,
        fields=("query", "url"),
        result_keys=("products",),
    ),
    "Product Details": Endpoint(
        path="/api/v1/capterra/product",
        credits=2,
        fields=("product_id", "slug", "url"),
    ),
    "Reviews": Endpoint(
        path="/api/v1/capterra/reviews",
        credits=2,
        fields=("product_id", "slug", "url", "page"),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioCapterraComponent(ScavioBaseComponent):
    display_name = "Scavio Capterra"
    description = (
        "Capterra through Scavio: search, product details, reviews (`/api/v1/capterra/*`, 2 credits each). Search "
        "Capterra for B2B software: 20 ranked products with name, vendor description, rating, review count, logo, "
        "paid-placement flag; each row carries product_id and slug."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioCapterra"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "query",
            "Query",
            (
                "Software product or category. Required unless you pass a url: a term-less search serves a fixed "
                "popular-products list that has nothing to do with the caller."
            ),
            tool_mode=True,
        ),
        text_input(
            "url",
            "URL",
            "Full capterra.com/search URL. capterra.co.uk and capterra.com.br are accepted.",
        ),
        text_input(
            "product_id",
            "Product ID",
            "The number in /p/186596/Notion/, as a STRING -- a JSON number is rejected.",
        ),
        text_input(
            "slug",
            "Slug",
            "Product slug. Cosmetic here: /p/186596/Zzzjunk/ returns Notion's profile byte for byte.",
        ),
        number_input(
            "page",
            "Page",
            "Result page, 1-100, at 25 reviews each. Past page 100 Capterra answers 200 with page ONE.",
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
