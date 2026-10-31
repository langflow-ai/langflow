from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DictInput, DropdownInput, MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute


class CompanyEnrichSimilarCountComponent(Component):
    display_name = "Count Similar Companies"
    description = (
        "Count Similar Companies with CompanyEnrich. One request; may consume credits. Full response preserved."
    )
    documentation = "https://docs.companyenrich.com/reference/post_companies-similar-count"
    icon = "CompanyEnrich"
    name = "CompanyEnrichSimilarCount"

    inputs = [
        *connection_inputs(),
        MessageTextInput(name="domains", display_name="Company Domains", is_list=True, required=True, tool_mode=True),
        DictInput(
            name="search_filters",
            display_name="Filters",
            advanced=True,
            info="Full API body filters; dedicated nonempty inputs and pagination take precedence",
        ),
        DropdownInput(
            name="wait_for_enrichment",
            display_name="Wait for Enrichment",
            options=["API default", "Wait", "Return immediately"],
            value="API default",
            advanced=True,
        ),
    ]
    outputs = [Output(display_name="Results", name="results", method="count_similar")]

    async def count_similar(self) -> Data:
        values = {
            "domains": self.domains,
            "filters": self.search_filters,
            "wait_for_enrichment": {"API default": None, "Wait": True, "Return immediately": False}[
                self.wait_for_enrichment
            ],
        }
        return await execute(self, "post_companies_similar_count", values)
