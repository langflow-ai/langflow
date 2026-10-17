"""YouTube License Labels component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import YouTubeTrainabilityInput


class FlashDataYouTubeTrainabilityComponent(FlashDataQueryComponent):
    display_name = "FlashData YouTube License Labels"
    description = (
        "Record a YouTube license-label signal. permitted is a license-label signal, not legal training "
        "permission or creator third-party training settings. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/youtube_trainability"
    name = "FlashDataYouTubeTrainability"
    source = "youtube_trainability"
    input_model = YouTubeTrainabilityInput
    primary = "video_id"
    inputs = component_inputs("video_id", YouTubeTrainabilityInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_youtube_trainability")]

    async def flashdata_youtube_trainability(self) -> Data:
        return await self.execute()
