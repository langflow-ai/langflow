"""Google Shopping component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import GoogleInput


class FlashDataGoogleShoppingComponent(FlashDataQueryComponent):
    display_name = "FlashData Google Shopping"
    description = (
        "Prepare a product offer comparison. Prices are search snapshots; inventory and checkout price "
        "are not guaranteed. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/google_shopping"
    name = "FlashDataGoogleShopping"
    source = "google_shopping"
    input_model = GoogleInput
    primary = "query"
    inputs = component_inputs("query", GoogleInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_google_shopping")]

    async def flashdata_google_shopping(self) -> Data:
        return await self.execute()
