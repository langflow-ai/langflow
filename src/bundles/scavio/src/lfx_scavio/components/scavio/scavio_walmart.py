from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output

from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    ScavioAPIMixin,
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
    "Product Search": Endpoint(
        path="/api/v1/walmart/search",
        credits=1,
        fields=(
            "query",
            "domain",
            "device",
            "sort_by",
            "start_page",
            "min_price",
            "max_price",
            "fulfillment_speed",
            "fulfillment_type",
            "delivery_zip",
            "store_id",
        ),
        required=("query",),
        result_keys=("products",),
    ),
    "Product Details": Endpoint(
        path="/api/v1/walmart/product",
        credits=1,
        fields=("product_id", "domain", "device", "delivery_zip", "store_id"),
        required=("product_id",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioWalmartComponent(ScavioAPIMixin, Component):
    display_name = "Scavio Walmart"
    description = (
        "Walmart through Scavio: keyword search and product details (`/api/v1/walmart/*`, 1 credit each). "
        "Product details is keyed on product_id, and search pages with start_page - there is no page field."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioWalmart"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Product Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Product Search"),
        text_input("query", "Search Query", "Keywords to search Walmart for.", tool_mode=True),
        text_input("product_id", "Product ID", "Walmart product id, e.g. 123456789.", tool_mode=True),
        choice_input(
            "device", "Device", "Device profile to emulate.", ["", "desktop", "mobile", "tablet"], advanced=True
        ),
        choice_input(
            "sort_by",
            "Sort By",
            "Result ordering for Product Search.",
            ["", "best_match", "price_low", "price_high", "best_seller"],
            advanced=True,
        ),
        number_input("start_page", "Start Page", "1-based results page. Walmart has no page field."),
        number_input("min_price", "Min Price", "Lower price bound. 0 means no bound."),
        number_input("max_price", "Max Price", "Upper price bound. 0 means no bound."),
        choice_input(
            "fulfillment_speed",
            "Fulfillment Speed",
            "How fast the item must be available.",
            ["", "today", "tomorrow", "2_days", "anytime"],
            advanced=True,
        ),
        choice_input(
            "fulfillment_type",
            "Fulfillment Type",
            "Restrict to in-store availability.",
            ["", "in_store"],
            advanced=True,
        ),
        text_input("delivery_zip", "Delivery ZIP", "ZIP code used for delivery and availability.", advanced=True),
        text_input("store_id", "Store ID", "Walmart store id used for availability.", advanced=True),
        text_input("domain", "Domain", "Walmart domain override.", advanced=True),
        max_results_input(),
    ]

    # The endpoint dropdown's default decides what is visible before the user
    # touches anything; update_build_config takes over from there.
    default_visibility(inputs, ENDPOINTS, DEFAULT_ENDPOINT)

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]
