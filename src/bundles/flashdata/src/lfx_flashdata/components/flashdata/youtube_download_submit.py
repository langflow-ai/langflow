"""YouTube Download Submit component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataDownloadSubmitComponent, component_inputs
from lfx_flashdata._inputs import YouTubeDownloadInput


class FlashDataYouTubeDownloadSubmitComponent(FlashDataDownloadSubmitComponent):
    display_name = "FlashData YouTube Download Submit"
    description = (
        "Track a YouTube delivery to customer cloud storage. Paid asynchronous job. Requires customer "
        "storage. Save the receipt; never submit again to poll. Result JSON expires after 24 hours; "
        "media retention depends on storage. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/youtube_download"
    name = "FlashDataYouTubeDownloadSubmit"
    source = "youtube_download"
    input_model = YouTubeDownloadInput
    primary = "video_id"
    inputs = component_inputs("video_id", YouTubeDownloadInput, action="submit")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_youtube_download_submit")]

    async def flashdata_youtube_download_submit(self) -> Data:
        return await self.execute()
