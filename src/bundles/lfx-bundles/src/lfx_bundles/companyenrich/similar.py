from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DictInput, DropdownInput, MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute, pagination_inputs


class CompanyEnrichSimilarComponent(Component):
    display_name = "Find Similar Companies"
    description = (
        "Find Similar Companies with CompanyEnrich. One request; may consume credits. Full response preserved."
    )
    documentation = "https://docs.companyenrich.com/reference/post_companies-similar"
    icon = "CompanyEnrich"
    name = "CompanyEnrichSimilar"

    inputs = [
        *connection_inputs(),
        MessageTextInput(name="domains", display_name="Company Domains", is_list=True, required=True, tool_mode=True),
        DictInput(
            name="search_filters",
            display_name="Filters",
            advanced=True,
            info="Full API body filters; dedicated nonempty inputs and pagination take precedence",
        ),
        MessageTextInput(
            name="expand",
            display_name="Expand",
            is_list=True,
            advanced=True,
            info="workforce for company routes; education for people",
        ),
        DropdownInput(
            name="wait_for_enrichment",
            display_name="Wait for Enrichment",
            options=["API default", "Wait", "Return immediately"],
            value="API default",
            advanced=True,
        ),
        *pagination_inputs(),
    ]
    outputs = [Output(display_name="Results", name="results", method="find_similar_companies")]

    async def find_similar_companies(self) -> Data:
        values = {
            "domains": self.domains,
            "filters": self.search_filters,
            "expand": self.expand or None,
            "wait_for_enrichment": {"API default": None, "Wait": True, "Return immediately": False}[
                self.wait_for_enrichment
            ],
            "page": self.page,
            "page_size": self.page_size,
        }
        return await execute(self, "post_companies_similar", values)
