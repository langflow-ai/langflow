"""YouTube Suggestions component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import YouTubeSuggestionsInput


class FlashDataYouTubeSuggestionsComponent(FlashDataQueryComponent):
    display_name = "FlashData YouTube Suggestions"
    description = (
        "Expand topic ideas with YouTube autocomplete. Suggestions are not keyword volume or popularity "
        "measurements. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/youtube_suggestions"
    name = "FlashDataYouTubeSuggestions"
    source = "youtube_suggestions"
    input_model = YouTubeSuggestionsInput
    primary = "query"
    inputs = component_inputs("query", YouTubeSuggestionsInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_youtube_suggestions")]

    async def flashdata_youtube_suggestions(self) -> Data:
        return await self.execute()
