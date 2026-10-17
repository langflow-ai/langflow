"""YouTube Search Extended component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import YouTubeExtendedSearchInput


class FlashDataYouTubeSearchExtendedComponent(FlashDataQueryComponent):
    display_name = "FlashData YouTube Search Extended"
    description = (
        "Build a larger YouTube research candidate set. This is a distinct source with a separate higher"
        " rate than standard search. Requested count is not guaranteed. FlashData API calls use paid "
        "Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/youtube_search_extended"
    name = "FlashDataYouTubeSearchExtended"
    source = "youtube_search_extended"
    input_model = YouTubeExtendedSearchInput
    primary = "query"
    inputs = component_inputs("query", YouTubeExtendedSearchInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_youtube_search_extended")]

    async def flashdata_youtube_search_extended(self) -> Data:
        return await self.execute()
