"""YouTube Metadata component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import YouTubeMetadataInput


class FlashDataYouTubeMetadataComponent(FlashDataQueryComponent):
    display_name = "FlashData YouTube Metadata"
    description = (
        "Inspect a video before adding it to a knowledge base. Metadata is not media download. Chapters "
        "and optional fields may be absent. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/youtube_metadata"
    name = "FlashDataYouTubeMetadata"
    source = "youtube_metadata"
    input_model = YouTubeMetadataInput
    primary = "video_id"
    inputs = component_inputs("video_id", YouTubeMetadataInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_youtube_metadata")]

    async def flashdata_youtube_metadata(self) -> Data:
        return await self.execute()
