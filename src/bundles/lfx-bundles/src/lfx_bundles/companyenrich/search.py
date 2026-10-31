from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DictInput, MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.companyenrich._client import connection_inputs, pagination_inputs, request, search_payload

MAX_QUERY_LENGTH = 500
MAX_SEARCH_RESULTS = 10_000


class CompanyEnrichSearchComponent(Component):
    display_name = "Search Companies"
    description = "Find companies using a natural-language query and filters. Results consume CompanyEnrich credits."
    documentation = "https://docs.companyenrich.com/reference/post_companies-search"
    icon = "CompanyEnrich"
    name = "CompanyEnrichSearch"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            tool_mode=True,
            info="Natural-language company description, up to 500 characters. Provide a query or filters.",
        ),
        DictInput(
            name="search_filters",
            display_name="Filters",
            advanced=True,
            info="Company Search API fields, such as countries and technologies. See the API reference.",
        ),
        *pagination_inputs(),
    ]
    outputs = [Output(display_name="Results", name="results", method="search_companies")]

    async def search_companies(self) -> Data:
        payload = search_payload(self.search_filters, self.page, self.page_size)
        if self.page * self.page_size > MAX_SEARCH_RESULTS:
            msg = "Page multiplied by Results Per Page cannot exceed 10,000 for company search."
            raise ValueError(msg)
        query = (self.query or "").strip()
        if len(query) > MAX_QUERY_LENGTH:
            msg = "Search Query must contain at most 500 characters."
            raise ValueError(msg)
        if not query and not self.search_filters:
            msg = "Provide a Search Query or at least one filter."
            raise ValueError(msg)
        if query:
            payload["semanticQuery"] = query
        result = await request(self.api_key, "POST", "/companies/search", timeout=self.timeout, payload=payload)
        self.status = result
        return Data(data=result)
