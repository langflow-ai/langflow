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
    text_input,
)

ENDPOINTS = {
    "Extract URL": Endpoint(
        path="/api/v1/extract",
        credits=1,
        fields=("url", "format", "mode"),
        required=("url",),
        credit_note=(
            "Costs 1 credit in normal or advanced mode and 2 credits in ultra mode, and is billed only on a "
            "successful extraction."
        ),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioExtractComponent(ScavioBaseComponent):
    display_name = "Scavio Extract"
    description = (
        "Extract through Scavio: extract url (`/api/v1/extract`; costs 1 credit in normal or advanced mode and 2 "
        "credits in ultra mode, and is billed only on a successful extraction). Read ANY URL and get it back as raw "
        "HTML, readability Markdown, or plain text. The read-a-page primitive: { url, format, mode, content, "
        "content_length }."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioExtract"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Extract URL"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Extract URL"),
        text_input(
            "url",
            "URL",
            (
                "Page to read. http(s) only; a bare host is upgraded to https. Loopback, private, link-local and "
                "metadata hosts are rejected with a 400."
            ),
            tool_mode=True,
        ),
        choice_input(
            "format",
            "Format",
            (
                "Output format: html is the raw page, markdown is a readability extraction, text is that markdown "
                "flattened to plain text. Options: html, markdown, text. Default: markdown."
            ),
            ["", "html", "markdown", "text"],
            advanced=True,
        ),
        choice_input(
            "mode",
            "Mode",
            (
                "Fetch tier and THE PRICE-BEARING PARAMETER: normal and advanced cost 1 credit, ultra costs 2. "
                "Escalate only when a plain fetch comes back empty. Options: normal, advanced, ultra. Default: "
                "normal."
            ),
            ["", "normal", "advanced", "ultra"],
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
