from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    IntInput,
    MessageTextInput,
    api_key_input,
    max_results_input,
)

ENDPOINTS = {
    "Google News": Endpoint(
        path="/api/v2/google/news",
        credits=1,
        fields=(
            "query",
            "topic_token",
            "section_token",
            "story_token",
            "publication_token",
            "kgmid",
            "hl",
            "gl",
            "google_domain",
            "so",
        ),
        result_keys=("news_results",),
    ),
}


class ScavioGoogleNewsComponent(ScavioBaseComponent):
    display_name = "Scavio Google News"
    description = (
        "Google News through Scavio (`POST /api/v2/google/news`, 1 credit). Drive it with exactly one of "
        "Query, Topic Token, Section Token, Story Token, Publication Token or KGMID."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioGoogleNews"

    ENDPOINTS = ENDPOINTS
    DEFAULT_ENDPOINT = "Google News"

    inputs = [
        api_key_input(),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="News search keywords. Supply exactly one driver: this, a token, or a KGMID.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="topic_token",
            display_name="Topic Token",
            info="Topic token from a previous News response.",
            advanced=True,
        ),
        MessageTextInput(
            name="section_token",
            display_name="Section Token",
            info="Section token from a previous News response.",
            advanced=True,
        ),
        MessageTextInput(
            name="story_token",
            display_name="Story Token",
            info="Story token from a previous News response.",
            advanced=True,
        ),
        MessageTextInput(
            name="publication_token",
            display_name="Publication Token",
            info="Publication token from a previous News response.",
            advanced=True,
        ),
        MessageTextInput(
            name="kgmid",
            display_name="KGMID",
            info="Knowledge Graph entity id, e.g. /m/02_286.",
            advanced=True,
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
        IntInput(
            name="so",
            display_name="Sort Order",
            info="1 sorts by date. 0 (the default) sorts by relevance. Only valid with Query or KGMID.",
            value=0,
            advanced=True,
        ),
        max_results_input(),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]
