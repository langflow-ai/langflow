"""YouTube Download Status component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataJobComponent, component_inputs
from lfx_flashdata._inputs import DownloadJobInput


class FlashDataYouTubeDownloadStatusComponent(FlashDataJobComponent):
    display_name = "FlashData YouTube Download Status"
    description = "Read a saved YouTube download job. Never submits, polls, or writes customer storage."
    documentation = "https://flashdata.dev/docs/sources/youtube_download"
    name = "FlashDataYouTubeDownloadStatus"
    action = "status"
    source = "youtube_download"
    input_model = DownloadJobInput
    primary = "job_id"
    inputs = component_inputs("job_id", DownloadJobInput, action="status")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_youtube_download_status")]

    async def flashdata_youtube_download_status(self) -> Data:
        return await self.execute()
