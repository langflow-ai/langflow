"""YouTube Search component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import YouTubeSearchInput


class FlashDataYouTubeSearchComponent(FlashDataQueryComponent):
    display_name = "FlashData YouTube Search"
    description = (
        "Find YouTube tutorials for a learning agent. The requested count is a ceiling, not a guaranteed"
        " result count. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/youtube_search"
    name = "FlashDataYouTubeSearch"
    source = "youtube_search"
    input_model = YouTubeSearchInput
    primary = "query"
    inputs = component_inputs("query", YouTubeSearchInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_youtube_search")]

    async def flashdata_youtube_search(self) -> Data:
        return await self.execute()
