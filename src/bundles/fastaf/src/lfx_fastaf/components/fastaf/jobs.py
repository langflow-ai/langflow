from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_fastaf._base import FastAFBaseComponent, require_text
from lfx_fastaf._inputs import (
    api_key_input,
    localization_inputs,
    query_input,
    text_input,
)


class FastAFJobsComponent(FastAFBaseComponent):
    display_name = "FastAF Search Jobs"
    description = "Retrieve one Google Jobs results page for 5 credits."
    name = "FastAFJobs"
    endpoint = "jobs"
    result_keys = ("jobs_results",)
    inputs = [
        api_key_input(),
        query_input(),
        *localization_inputs(),
        text_input(
            "next_page_token",
            "Next Page Token",
            "Continuation token; keep the same query and filters. Each page costs 5 credits.",
            advanced=True,
        ),
        text_input(
            "filters", "Job Filters", "Google Jobs chips expression, e.g. employment_type:FULLTIME.", advanced=True
        ),
    ]
    outputs = [Output(display_name="Table", name="dataframe", method="fastaf_jobs")]

    def request_body(self) -> dict:
        return {
            "query": require_text(self.query, "Search Query"),
            **self.localization(),
            "next_page_token": self.next_page_token,
            "chips": self.filters,
        }

    def fastaf_jobs(self) -> DataFrame:
        return DataFrame(self.fetch_content())
