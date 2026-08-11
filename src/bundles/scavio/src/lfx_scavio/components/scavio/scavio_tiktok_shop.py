from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    BoolInput,
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
        path="/api/v1/tiktok-shop/search",
        credits=1,
        fields=("search", "cursor"),
        required=("search",),
        result_keys=("products",),
    ),
    "Search Suggestions": Endpoint(
        path="/api/v1/tiktok-shop/search/suggestions",
        credits=1,
        fields=("search", "region"),
        required=("search",),
        result_keys=("suggestions",),
    ),
    "Product Details": Endpoint(
        path="/api/v1/tiktok-shop/product",
        credits=1,
        fields=("product_id", "region"),
        required=("product_id",),
    ),
    "Product Reviews": Endpoint(
        path="/api/v1/tiktok-shop/product/reviews",
        credits=1,
        fields=("product_id", "page", "page_size", "sort", "rating", "has_media", "verified_only", "region"),
        required=("product_id",),
        result_keys=("reviews",),
    ),
    "Categories": Endpoint(
        path="/api/v1/tiktok-shop/categories",
        credits=1,
        result_keys=("categories",),
    ),
    "Category Products": Endpoint(
        path="/api/v1/tiktok-shop/category/products",
        credits=1,
        fields=("category_id", "cursor", "region"),
        required=("category_id",),
        result_keys=("products",),
    ),
    "Shop Products": Endpoint(
        path="/api/v1/tiktok-shop/shop/products",
        credits=1,
        fields=("shop_id", "cursor", "region"),
        required=("shop_id",),
        result_keys=("products",),
    ),
    "Resolve URL": Endpoint(
        path="/api/v1/tiktok-shop/resolve",
        credits=1,
        fields=("url",),
        required=("url",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioTikTokShopComponent(ScavioBaseComponent):
    display_name = "Scavio TikTok Shop"
    description = (
        "The full Scavio TikTok Shop surface: catalog search, suggestions, product details and reviews, "
        "the category tree, category and shop listings, and the share-link resolver "
        "(`/api/v1/tiktok-shop/*`, 1 credit each). Prices on Product Details are masked upstream and come "
        "back null - use Search or Shop Products for exact prices."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioTikTokShop"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "search",
            "Search",
            "The keyword. TikTok Shop's wire field is search, not query. Search itself is US-catalog only.",
            tool_mode=True,
        ),
        text_input("product_id", "Product ID", "Numeric TikTok Shop product id.", tool_mode=True),
        text_input(
            "category_id",
            "Category ID",
            "Category id from the Categories endpoint. Level 1 or 2 both work.",
            tool_mode=True,
        ),
        text_input("shop_id", "Shop ID", "TikTok Shop seller id.", tool_mode=True),
        text_input(
            "url",
            "URL",
            "A shop.tiktok.com product or store page, a tiktok.com/view link, an affiliate share link, or a "
            "vt.tiktok.com short link.",
            tool_mode=True,
        ),
        cursor_input("Opaque cursor echoed from a previous response's next_cursor."),
        choice_input(
            "region",
            "Region",
            "Marketplace region. Category Products supports US and GB only; Search takes no region at all.",
            ["", "US", "GB", "SG", "MY", "PH", "TH", "VN", "ID"],
            advanced=True,
        ),
        number_input("page", "Page", "1-based review page, 1 to 500.", value=1),
        number_input("page_size", "Page Size", "Reviews per page, 1 to 200.", value=20),
        choice_input(
            "sort",
            "Review Sort",
            "relevant returns text-complete, image-heavy reviews; recent is fresher but sparser.",
            ["", "relevant", "recent"],
            advanced=True,
        ),
        number_input("rating", "Rating Filter", "Keep only reviews with this star rating, 1 to 5. 0 means no filter."),
        BoolInput(
            name="has_media",
            display_name="Has Media",
            info="Only reviews with a photo or video. Wins over Verified Only - they share one upstream slot.",
            value=False,
            advanced=True,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="verified_only",
            display_name="Verified Only",
            info="Only verified purchases. Ignored when Has Media is on.",
            value=False,
            advanced=True,
            dynamic=True,
            show=False,
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
