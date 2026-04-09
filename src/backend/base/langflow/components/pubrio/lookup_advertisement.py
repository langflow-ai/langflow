import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioLookupAdvertisementComponent(Component):
    display_name = "Pubrio Lookup Advertisement"
    description = "Look up detailed information about a specific advertisement."
    icon = "megaphone"
    name = "PubrioLookupAdvertisement"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(
            name="id",
            display_name="Advertisement Search ID",
            info="The advertisement_search_id.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="lookup"),
    ]

    def lookup(self) -> DataFrame:
        result = pubrio_post(self.api_key, "/companies/advertisements/lookup", {"advertisement_search_id": self.id})
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
