from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    ScavioAPIMixin,
    api_key_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Product Search": Endpoint(
        path="/api/v1/amazon/search",
        credits=1,
        fields=("query", "country", "page"),
        required=("query",),
        result_keys=("products",),
    ),
    "Product Details": Endpoint(
        path="/api/v1/amazon/product",
        credits=1,
        fields=("asin", "country"),
        required=("asin",),
    ),
    "Offer Listing": Endpoint(
        path="/api/v1/amazon/offers",
        credits=1,
        fields=("asin", "country"),
        required=("asin",),
        result_keys=("offers",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioAmazonComponent(ScavioAPIMixin, Component):
    display_name = "Scavio Amazon"
    description = (
        "Amazon through Scavio: keyword search, product details and the offer listing that carries the "
        "buy box (`/api/v1/amazon/*`, 1 credit each). Marketplace is picked with a two-letter country "
        "code - amazon.com is us and amazon.co.uk is gb."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioAmazon"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Product Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Product Search"),
        text_input("query", "Search Query", "Keywords to search the marketplace for.", tool_mode=True),
        text_input(
            "asin",
            "ASIN",
            "The product ASIN, e.g. B09V3KXJPB. Older Scavio clients send this in query; both are accepted.",
            tool_mode=True,
        ),
        text_input(
            "country",
            "Marketplace Country",
            "Two-letter marketplace code, e.g. us, gb, de, jp. Defaults to us. Not a zip and not a domain.",
            advanced=True,
        ),
        number_input("page", "Page", "1-based results page for Product Search."),
        max_results_input(),
    ]

    # The endpoint dropdown's default decides what is visible before the user
    # touches anything; update_build_config takes over from there.
    default_visibility(inputs, ENDPOINTS, DEFAULT_ENDPOINT)

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]
