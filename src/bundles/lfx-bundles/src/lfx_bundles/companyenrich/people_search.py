from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DictInput, MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, execute, pagination_inputs


class CompanyEnrichPeopleSearchComponent(Component):
    display_name = "Search People"
    description = "Search People with CompanyEnrich. One request; may consume credits. Full response preserved."
    documentation = "https://docs.companyenrich.com/reference/post_people-search"
    icon = "CompanyEnrich"
    name = "CompanyEnrichPeopleSearch"

    inputs = [
        *connection_inputs(),
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
        *pagination_inputs(),
    ]
    outputs = [Output(display_name="Results", name="results", method="search_people")]

    async def search_people(self) -> Data:
        values = {
            "filters": self.search_filters,
            "expand": self.expand or None,
            "page": self.page,
            "page_size": self.page_size,
        }
        return await execute(self, "post_people_search", values)
