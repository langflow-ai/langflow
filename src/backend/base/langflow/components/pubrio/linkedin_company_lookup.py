import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioLinkedInCompanyLookupComponent(Component):
    display_name = "Pubrio LinkedIn Company Lookup"
    description = "Look up a company by its LinkedIn URL."
    icon = "linkedin"
    name = "PubrioLinkedInCompanyLookup"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(name="linkedin_url", display_name="LinkedIn URL", info="LinkedIn company page URL.", required=True, tool_mode=True),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run_lookup"),
    ]

    def run_lookup(self) -> DataFrame:
        result = pubrio_post(self.api_key, "/companies/linkedin/lookup", {"linkedin_url": self.linkedin_url})
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
