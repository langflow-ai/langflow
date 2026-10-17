"""Google News component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import GoogleInput


class FlashDataGoogleNewsComponent(FlashDataQueryComponent):
    display_name = "FlashData Google News"
    description = (
        "Prepare a dated news briefing. Returns news search results, not article full text. FlashData "
        "API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/google_news"
    name = "FlashDataGoogleNews"
    source = "google_news"
    input_model = GoogleInput
    primary = "query"
    inputs = component_inputs("query", GoogleInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_google_news")]

    async def flashdata_google_news(self) -> Data:
        return await self.execute()
