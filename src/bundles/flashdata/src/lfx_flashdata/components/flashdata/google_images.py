"""Google Images component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import GoogleInput


class FlashDataGoogleImagesComponent(FlashDataQueryComponent):
    display_name = "FlashData Google Images"
    description = (
        "Build an image research shortlist. Does not download images or establish image reuse rights. "
        "FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/google_images"
    name = "FlashDataGoogleImages"
    source = "google_images"
    input_model = GoogleInput
    primary = "query"
    inputs = component_inputs("query", GoogleInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_google_images")]

    async def flashdata_google_images(self) -> Data:
        return await self.execute()
