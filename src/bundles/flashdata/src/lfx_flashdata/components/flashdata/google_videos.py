"""Google Videos component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import GoogleInput


class FlashDataGoogleVideosComponent(FlashDataQueryComponent):
    display_name = "FlashData Google Videos"
    description = (
        "Find video references across websites. Search discovers videos; it does not return video files "
        "or transcripts. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/google_videos"
    name = "FlashDataGoogleVideos"
    source = "google_videos"
    input_model = GoogleInput
    primary = "query"
    inputs = component_inputs("query", GoogleInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_google_videos")]

    async def flashdata_google_videos(self) -> Data:
        return await self.execute()
