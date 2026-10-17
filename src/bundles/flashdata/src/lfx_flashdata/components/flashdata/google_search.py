"""Google Search component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import GoogleInput


class FlashDataGoogleSearchComponent(FlashDataQueryComponent):
    display_name = "FlashData Google Search"
    description = (
        "Find web evidence for an AI research agent. Search snippets are not fetched page content. "
        "Omitted count and locale are not filled in by the SDK. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/google_search"
    name = "FlashDataGoogleSearch"
    source = "google_search"
    input_model = GoogleInput
    primary = "query"
    inputs = component_inputs("query", GoogleInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_google_search")]

    async def flashdata_google_search(self) -> Data:
        return await self.execute()
