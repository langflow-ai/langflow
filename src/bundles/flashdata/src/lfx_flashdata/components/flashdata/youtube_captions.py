"""YouTube Captions component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import YouTubeCaptionsInput


class FlashDataYouTubeCaptionsComponent(FlashDataQueryComponent):
    display_name = "FlashData YouTube Captions"
    description = (
        "Review uploader captions for a content brief. Defaults to uploader captions. No ASR, "
        "translation, or automatic fallback to generated captions. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/youtube_captions"
    name = "FlashDataYouTubeCaptions"
    source = "youtube_captions"
    input_model = YouTubeCaptionsInput
    primary = "video_id"
    inputs = component_inputs("video_id", YouTubeCaptionsInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_youtube_captions")]

    async def flashdata_youtube_captions(self) -> Data:
        return await self.execute()
