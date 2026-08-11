from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    choice_input,
    default_visibility,
    endpoint_input,
    flag_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Ticker Lookup": Endpoint(
        path="/api/v1/sec/lookup",
        credits=1,
        fields=("query", "limit", "exchange"),
        required=("query",),
        result_keys=("results",),
    ),
    "Company Details": Endpoint(
        path="/api/v1/sec/company",
        credits=1,
        fields=("cik", "ticker"),
    ),
    "Filings": Endpoint(
        path="/api/v1/sec/filings",
        credits=1,
        fields=("cik", "ticker", "form", "date_from", "date_to", "page", "limit", "include_history"),
        result_keys=("filings",),
    ),
    "Concept": Endpoint(
        path="/api/v1/sec/concept",
        credits=1,
        fields=("cik", "ticker", "concept", "taxonomy", "unit", "form", "limit"),
        required=("concept",),
        result_keys=("facts",),
    ),
    "Facts": Endpoint(
        path="/api/v1/sec/facts",
        credits=1,
        fields=("cik", "ticker", "taxonomy", "query", "limit"),
        result_keys=("concepts",),
    ),
    "Search": Endpoint(
        path="/api/v1/sec/search",
        credits=1,
        fields=("query", "cik", "ticker", "form", "date_from", "date_to", "location", "sort", "page"),
        result_keys=("results",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioSecComponent(ScavioBaseComponent):
    display_name = "Scavio SEC EDGAR"
    description = (
        "SEC EDGAR through Scavio: ticker lookup, company details, filings, concept, facts, search (`/api/v1/sec/*`, "
        "1 credit each). START HERE. Resolve a company name or ticker (AAPL) to the CIK (0000320193) every other SEC "
        "EDGAR endpoint is keyed by."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioSec"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Ticker Lookup"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Ticker Lookup"),
        text_input(
            "query",
            "Query",
            "Ticker, company name, or a fragment of either.",
            tool_mode=True,
        ),
        number_input(
            "limit",
            "Limit",
            "Maximum filers to return, 1-100. Default: 10.",
        ),
        text_input(
            "exchange",
            "Exchange",
            (
                "Listing exchange filter, matched case-insensitively. Filers listed with no exchange are excluded "
                "by any value. Options: NASDAQ, NYSE, OTC, CBOE."
            ),
        ),
        text_input(
            "cik",
            "CIK",
            "Central Index Key: 320193, 0000320193 or CIK0000320193. A ticker is accepted here too.",
        ),
        text_input(
            "ticker",
            "Ticker",
            "Stock ticker, dotted or dashed (BRK.B / BRK-B). WINS over cik when both are given.",
        ),
        text_input(
            "form",
            "Form",
            (
                'Form filter: "10-K", ["10-K", "10-Q"] or "10-K,8-K". Matched against the form AND its root form, '
                "so 10-K also returns 10-K/A amendments."
            ),
        ),
        text_input(
            "date_from",
            "Date From",
            "Earliest date to include, YYYY-MM-DD.",
        ),
        text_input(
            "date_to",
            "Date To",
            "Latest date to include, YYYY-MM-DD.",
        ),
        number_input(
            "page",
            "Page",
            "Result page number, 1-based.",
        ),
        flag_input(
            "include_history",
            "Include History",
            (
                "Also read the archived filing shards (up to 10). Still one credit; history_truncated flags a filer "
                "that had more. Default: False."
            ),
        ),
        text_input(
            "concept",
            "Concept",
            (
                "XBRL tag, CASE-SENSITIVE: 'netincomeloss' is a 404 upstream, not a match. Use the facts endpoint "
                "to list what a filer actually reports."
            ),
        ),
        text_input(
            "taxonomy",
            "Taxonomy",
            "XBRL taxonomy: us-gaap, dei, ifrs-full or srt. Default: us-gaap.",
        ),
        text_input(
            "unit",
            "Unit",
            "Unit of measure to filter on, e.g. USD or USD/shares.",
        ),
        text_input(
            "location",
            "Location",
            (
                "EDGAR's own jurisdiction codes: CA, NY, and alphanumeric codes for foreign jurisdictions. One code "
                "or a list."
            ),
        ),
        choice_input(
            "sort",
            "Sort",
            "Sort order for the results. Options: relevance, newest, oldest. Default: relevance.",
            ["", "relevance", "newest", "oldest"],
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
