from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput
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
    "Shopping Search": Endpoint(
        path="/api/v2/google/shopping",
        credits=1,
        fields=(
            "query",
            "device",
            "start",
            "min_price",
            "max_price",
            "sort_by",
            "free_shipping",
            "on_sale",
            "shoprs",
            "hl",
            "gl",
            "google_domain",
            "location",
            "uule",
        ),
        required=("query",),
        result_keys=("shopping_results",),
    ),
    "Product Details": Endpoint(
        path="/api/v2/google/shopping/product",
        credits=1,
        fields=(
            "catalog_id",
            "query",
            "product_id",
            "immersive_product_page_token",
            "page_token",
            "device",
            "product_sort_by",
            "load_all_stores",
            "more_stores",
            "hl",
            "gl",
            "google_domain",
            "location",
            "uule",
        ),
        result_keys=("product_results",),
        wire={"product_sort_by": "sort_by"},
    ),
    "Product Stores": Endpoint(
        path="/api/v2/google/shopping/product/stores",
        credits=1,
        fields=("catalog_id", "next_page_token"),
        required=("catalog_id", "next_page_token"),
        result_keys=("product_results.stores",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioGoogleShoppingComponent(ScavioAPIMixin, Component):
    display_name = "Scavio Google Shopping"
    description = (
        "Google Shopping through Scavio: product search, product details and the full store list for a "
        "product (`/api/v2/google/shopping*`, 1 credit each)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioGoogleShopping"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Shopping Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Shopping Search"),
        text_input(
            "query",
            "Query",
            "Product keywords. On Product Details this is mandatory whenever a Catalog ID is supplied.",
            tool_mode=True,
        ),
        text_input("catalog_id", "Catalog ID", "Durable catalog id. Requires Query on Product Details."),
        text_input("product_id", "Product ID", "Google product id, an alternative driver on Product Details."),
        text_input(
            "immersive_product_page_token",
            "Immersive Product Page Token",
            "Token lifted from a shopping result. Page Token is an alias of this field.",
            advanced=True,
        ),
        text_input("page_token", "Page Token", "Alias of Immersive Product Page Token.", advanced=True),
        text_input(
            "next_page_token",
            "Next Page Token",
            "Store-list continuation cursor from a previous response.",
        ),
        choice_input(
            "device",
            "Device",
            "Device profile. tablet is accepted on Product Details only.",
            ["", "desktop", "mobile", "tablet"],
            advanced=True,
        ),
        number_input("start", "Start Offset", "Shopping result offset. Follow pagination.next."),
        number_input("min_price", "Min Price", "Lower price bound. 0 means no bound."),
        number_input("max_price", "Max Price", "Upper price bound. 0 means no bound."),
        number_input(
            "sort_by", "Sort By", "Shopping search order: 1 price ascending, 2 price descending. 0 relevance."
        ),
        choice_input(
            "product_sort_by",
            "Store Sort",
            "Seller ordering on Product Details. Sent to the API as sort_by.",
            ["", "base_price", "total_price", "promotion", "seller_rating"],
            advanced=True,
        ),
        text_input(
            "shoprs", "Shoprs Filter", "Opaque filter token taken from filters[] in a prior response.", advanced=True
        ),
        BoolInput(
            name="free_shipping",
            display_name="Free Shipping Only",
            info="Restrict shopping results to free-shipping offers.",
            value=False,
            advanced=True,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="on_sale",
            display_name="On Sale Only",
            info="Restrict shopping results to discounted offers.",
            value=False,
            advanced=True,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="load_all_stores",
            display_name="Load All Stores",
            info="Ask Product Details for the full store list rather than the first page.",
            value=False,
            advanced=True,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="more_stores",
            display_name="More Stores",
            info="Ask Product Details for the extended store list.",
            value=False,
            advanced=True,
            dynamic=True,
            show=False,
        ),
        text_input("gl", "Country (gl)", "Two-letter geo country code, e.g. us.", advanced=True),
        text_input("hl", "Language (hl)", "Two-letter interface language code, e.g. en.", advanced=True),
        text_input("google_domain", "Google Domain", "Google domain to query, e.g. google.co.uk.", advanced=True),
        text_input(
            "location", "Location", "Canonical location name, e.g. Austin, Texas, United States.", advanced=True
        ),
        text_input("uule", "UULE", "Pre-encoded UULE string. Takes priority over Location.", advanced=True),
        max_results_input(),
    ]

    # The endpoint dropdown's default decides what is visible before the user
    # touches anything; update_build_config takes over from there.
    default_visibility(inputs, ENDPOINTS, DEFAULT_ENDPOINT)

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]
