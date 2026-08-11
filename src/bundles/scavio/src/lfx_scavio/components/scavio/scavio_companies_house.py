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
        path="/api/v1/companieshouse/search",
        credits=1,
        fields=("query", "page"),
        required=("query",),
        result_keys=("results",),
    ),
    "Company Details": Endpoint(
        path="/api/v1/companieshouse/company",
        credits=1,
        fields=("company_number",),
        required=("company_number",),
    ),
    "Officers": Endpoint(
        path="/api/v1/companieshouse/officers",
        credits=1,
        fields=("company_number", "page"),
        required=("company_number",),
    ),
    "Filing History": Endpoint(
        path="/api/v1/companieshouse/filing-history",
        credits=1,
        fields=("company_number", "page"),
        required=("company_number",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioCompaniesHouseComponent(ScavioBaseComponent):
    display_name = "Scavio Companies House"
    description = (
        "Companies House through Scavio: search, company details, officers, filing history "
        "(`/api/v1/companieshouse/*`, 1 credit each). START HERE. Search the UK register by name and get the "
        "company_number every other endpoint is keyed by, plus status, incorporation date and registered office. "
        "Pagination: page -- 20 per page, CAPPED AT PAGE 50. The register serves a 1000-result WINDOW per term "
        "whatever hit count it prints (it claims 10,000 for a broad term then answers page 51 with HTTP 416)."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioCompaniesHouse"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "query",
            "Query",
            "Company name or number. Matches CURRENT AND FORMER names.",
            tool_mode=True,
        ),
        number_input(
            "page",
            "Page",
            (
                "Result page, 1-50, at 20 rows each. Capped at 50 because the register only serves the first 1000 "
                "matches per term whatever hit count it prints. Default: 1."
            ),
        ),
        text_input(
            "company_number",
            "Company Number",
            (
                "Company number. Zero-padded and upper-cased for you, so numbers off a letterhead or a spreadsheet "
                "that ate leading zeros still resolve. SC, NI, OC, SO, NC, FC, BR and CE prefixes are supported."
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
