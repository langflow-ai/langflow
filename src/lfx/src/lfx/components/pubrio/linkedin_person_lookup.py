import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioLinkedInPersonLookupComponent(Component):
    display_name = "Pubrio LinkedIn Person Lookup"
    description = "Real-time LinkedIn person lookup by URL."
    icon = "linkedin"
    name = "PubrioLinkedInPersonLookup"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(name="linkedin_url", display_name="LinkedIn URL", info="LinkedIn profile URL.", tool_mode=True),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run_lookup"),
    ]

    def run_lookup(self) -> DataFrame:
        result = pubrio_post(self.api_key, "/people/linkedin/lookup", {"linkedin_url": self.linkedin_url})
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
