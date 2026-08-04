from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, MessageTextInput
from lfx.template.field.base import Output
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    ScavioAPIMixin,
    api_key_input,
    max_results_input,
)

ENDPOINTS = {
    "Google AI Mode": Endpoint(
        path="/api/v2/google/ai-mode",
        credits=1,
        fields=("query", "device", "hl", "gl", "google_domain", "location", "uule", "safe", "include_html"),
        required=("query",),
        result_keys=("references",),
    ),
}


class ScavioGoogleAIModeComponent(ScavioAPIMixin, Component):
    display_name = "Scavio Google AI Mode"
    description = (
        "Run a Google AI Mode query through Scavio (`POST /api/v2/google/ai-mode`, 1 credit) and get the "
        "generated answer blocks plus the references Google cited."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioGoogleAIMode"

    ENDPOINTS = ENDPOINTS
    DEFAULT_ENDPOINT = "Google AI Mode"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="The question to send to Google AI Mode.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="gl",
            display_name="Country (gl)",
            info="Two-letter geo country code, e.g. us.",
            advanced=True,
        ),
        MessageTextInput(
            name="hl",
            display_name="Language (hl)",
            info="Two-letter interface language code, e.g. en.",
            advanced=True,
        ),
        MessageTextInput(
            name="google_domain",
            display_name="Google Domain",
            info="Google domain to query, e.g. google.co.uk.",
            advanced=True,
        ),
        MessageTextInput(
            name="location",
            display_name="Location",
            info="Canonical location name, e.g. Austin, Texas, United States.",
            advanced=True,
        ),
        MessageTextInput(
            name="uule",
            display_name="UULE",
            info="Pre-encoded UULE location string. Takes priority over Location.",
            advanced=True,
        ),
        DropdownInput(
            name="device",
            display_name="Device",
            info="Device profile to emulate.",
            options=["", "desktop", "mobile"],
            value="",
            advanced=True,
        ),
        DropdownInput(
            name="safe",
            display_name="Safe Search",
            info="Set to active to turn SafeSearch on.",
            options=["", "active"],
            value="",
            advanced=True,
        ),
        BoolInput(
            name="include_html",
            display_name="Include Raw HTML",
            info="Add Google's raw HTML to the response under the html key.",
            value=False,
            advanced=True,
        ),
        max_results_input(),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]
