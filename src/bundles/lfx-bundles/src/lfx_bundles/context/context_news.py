from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._client import context_api_key_input, request_context


class ContextSearchNewsComponent(Component):
    display_name = "Context.dev Company News"
    description = "Find recent company news by domain, name, ticker, or ISIN."
    documentation = "https://docs.context.dev/api-reference/news/search"
    icon = "Context"

    inputs = [
        context_api_key_input(),
        DropdownInput(
            name="identifier_type",
            display_name="Company Identifier",
            options=["domain", "name", "ticker", "isin"],
            value="domain",
        ),
        MessageTextInput(
            name="identifier",
            display_name="Identifier Value",
            info="Company domain, name, ticker, or ISIN, matching the selected identifier type.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="sort_by",
            display_name="Sort By",
            options=["newest", "relevance"],
            value="newest",
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Result Limit",
            value=10,
            range_spec=RangeSpec(min=1, max=100, step=1, step_type="int"),
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="News Results", name="results", method="search_news")]

    async def search_news(self) -> Data:
        identifier_type = str(self.identifier_type)
        identifier = str(self.identifier).strip()
        payload = {
            "searchBy": {
                "type": "entity",
                "entity": {"type": identifier_type, identifier_type: identifier},
            },
            "sortBy": {"type": self.sort_by},
            "limit": self.limit,
        }
        response = await request_context("POST", "/news/search", self.api_key, json=payload)
        self.status = response
        return Data(data=response)
