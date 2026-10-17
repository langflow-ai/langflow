"""Google Places component for FlashData."""

from lfx.schema.data import Data
from lfx.template.field.base import Output

from lfx_flashdata._base import FlashDataQueryComponent, component_inputs
from lfx_flashdata._inputs import GoogleInput


class FlashDataGooglePlacesComponent(FlashDataQueryComponent):
    display_name = "FlashData Google Places"
    description = (
        "Shortlist local businesses for a planning assistant. Contact details may be missing; verify "
        "current hours and availability with the business. FlashData API calls use paid Credits."
    )
    documentation = "https://flashdata.dev/docs/sources/google_places"
    name = "FlashDataGooglePlaces"
    source = "google_places"
    input_model = GoogleInput
    primary = "query"
    inputs = component_inputs("query", GoogleInput, action="query")
    outputs = [Output(display_name="JSON", name="data", method="flashdata_google_places")]

    async def flashdata_google_places(self) -> Data:
        return await self.execute()
