from lfx.inputs.inputs import BoolInput
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_fastaf._base import FastAFBaseComponent, boolean_option
from lfx_fastaf._inputs import (
    api_key_input,
    optional_bool,
    query_input,
    search_page_inputs,
    text_input,
)


class FastAFSearchComponent(FastAFBaseComponent):
    display_name = "FastAF Search Web"
    description = "One Google results page: 5 credits, or 10 with advanced search. No automatic pagination or retries."
    name = "FastAFSearch"
    endpoint = "serp"
    result_keys = ("organic_results",)
    inputs = [
        api_key_input(),
        query_input(),
        *search_page_inputs(),
        BoolInput(
            name="advanced_search", display_name="Advanced Search", value=False, info="10 rather than 5 credits."
        ),
        optional_bool("mobile", "Mobile Results", "Mobile instead of desktop results; no surcharge."),
        text_input(
            "location", "Search Origin", "City-level origin, such as Austin, Texas, United States.", advanced=True
        ),
    ]
    outputs = [Output(display_name="Table", name="dataframe", method="fastaf_search")]

    def request_body(self) -> dict:
        return {
            **self.search_page(),
            "advance_search": self.advanced_search,
            "mob_search": boolean_option(self.mobile),
            "location": self.location,
        }

    def fastaf_search(self) -> DataFrame:
        return DataFrame(self.fetch_content())
