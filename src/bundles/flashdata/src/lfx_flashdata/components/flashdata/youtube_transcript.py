"""YouTube Transcript component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import YouTubeTranscriptInput


class FlashDataYouTubeTranscriptComponent(FlashDataQueryComponent):
    display_name = "FlashData YouTube Transcript"
    description = (
        "Prepare timestamped video evidence for an agent. Reads an existing track. No ASR, translation, "
        "or automatic fallback to uploader captions. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/youtube_transcript"
    name = "FlashDataYouTubeTranscript"
    source = "youtube_transcript"
    input_model = YouTubeTranscriptInput
    primary = "video_id"
    inputs = component_inputs("video_id", YouTubeTranscriptInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_youtube_transcript")]

    async def flashdata_youtube_transcript(self) -> Data:
        return await self.execute()
