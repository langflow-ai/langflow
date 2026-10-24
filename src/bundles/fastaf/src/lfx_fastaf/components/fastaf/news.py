from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_fastaf._base import FastAFBaseComponent
from lfx_fastaf._inputs import (
    api_key_input,
    query_input,
    search_page_inputs,
    text_input,
)


class FastAFNewsComponent(FastAFBaseComponent):
    display_name = "FastAF Search News"
    description = "Retrieve one Google News results page for 5 credits."
    name = "FastAFNews"
    endpoint = "news"
    result_keys = ("news_results",)
    inputs = [
        api_key_input(),
        query_input(),
        *search_page_inputs(),
        text_input(
            "time_filter", "Time Filter", "Google expression: qdr:d (past day) or qdr:w (past week).", advanced=True
        ),
    ]
    outputs = [Output(display_name="Table", name="dataframe", method="fastaf_news")]

    def request_body(self) -> dict:
        return {**self.search_page(), "tbs": self.time_filter}

    def fastaf_news(self) -> DataFrame:
        return DataFrame(self.fetch_content())
