from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_fastaf._base import FastAFBaseComponent, FastAFError
from lfx_fastaf._inputs import (
    api_key_input,
    choice_input,
    scrape_inputs,
    text_input,
)


class FastAFScrapeComponent(FastAFBaseComponent):
    display_name = "FastAF Scrape Page"
    description = (
        "Retrieve public HTML, markdown, links, images or a summary. Static scrape: 1 credit; options can cost more."
    )
    name = "FastAFScrape"
    endpoint = "scrape"
    result_keys = ()
    inputs = [
        api_key_input(),
        *scrape_inputs(),
        choice_input(
            "format",
            "Output Format",
            ["html", "markdown", "links", "images", "summary"],
            "html",
            "One format; an AI summary adds 10 credits.",
        ),
        text_input(
            "session_number",
            "Proxy Session",
            "Repeat an ID to request the same proxy; expires after 60s idle.",
            advanced=True,
        ),
    ]
    outputs = [Output(display_name="Table", name="dataframe", method="fastaf_scrape")]

    def request_body(self) -> dict:
        if self.format not in {"html", "markdown", "links", "images", "summary"}:
            msg = "Unsupported scrape output format."
            raise FastAFError(msg)
        return {**self.scrape_body(), "formats": self.format, "session_number": self.session_number}

    def fastaf_scrape(self) -> DataFrame:
        return DataFrame(self.fetch_content())
