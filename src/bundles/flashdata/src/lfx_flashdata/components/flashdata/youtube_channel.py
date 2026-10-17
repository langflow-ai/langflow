"""YouTube Channel component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import YouTubeChannelInput


class FlashDataYouTubeChannelComponent(FlashDataQueryComponent):
    display_name = "FlashData YouTube Channel"
    description = (
        "Prepare a channel and recent-video briefing. A recent-video snapshot is not the complete "
        "channel archive. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/youtube_channel"
    name = "FlashDataYouTubeChannel"
    source = "youtube_channel"
    input_model = YouTubeChannelInput
    primary = "handle"
    inputs = component_inputs("handle", YouTubeChannelInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_youtube_channel")]

    async def flashdata_youtube_channel(self) -> Data:
        return await self.execute()
