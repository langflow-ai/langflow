from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DictInput, MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute


class CompanyEnrichSearchCountComponent(Component):
    display_name = "Count Company Search"
    description = "Count Company Search with CompanyEnrich. One request; may consume credits. Full response preserved."
    documentation = "https://docs.companyenrich.com/reference/post_companies-search-count"
    icon = "CompanyEnrich"
    name = "CompanyEnrichSearchCount"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            tool_mode=True,
            info="Semantic description, at most 500 characters",
        ),
        MessageTextInput(
            name="literal_query",
            display_name="Literal Query",
            advanced=True,
            info="Company name/domain text, at most 250 characters",
        ),
        DictInput(
            name="search_filters",
            display_name="Filters",
            advanced=True,
            info="Full API body filters; dedicated nonempty inputs and pagination take precedence",
        ),
    ]
    outputs = [Output(display_name="Results", name="results", method="count_companies")]

    async def count_companies(self) -> Data:
        values = {
            "semantic_query": self.query or None,
            "query": self.literal_query or None,
            "filters": self.search_filters,
        }
        return await execute(self, "post_companies_search_count", values)
