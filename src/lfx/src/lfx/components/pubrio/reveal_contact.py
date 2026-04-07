import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post, split_csv


class PubrioRevealContactComponent(Component):
    display_name = "Pubrio Reveal Contact"
    description = "Reveal verified email or phone for a person (uses credits)."
    icon = "mail"
    name = "PubrioRevealContact"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(name="query", display_name="Query", info="JSON with lookup_type, value, and people_contact_types.", tool_mode=True),
        DropdownInput(name="lookup_type", display_name="Lookup Type", options=["linkedin_url", "people_search_id"], value="people_search_id"),
        MessageTextInput(name="value", display_name="Value", info="LinkedIn URL or people_search_id."),
        MessageTextInput(name="people_contact_types", display_name="Contact Types", info="Comma-separated: email-work, email-personal, phone", value="email-work"),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="reveal"),
    ]

    def reveal(self) -> DataFrame:
        lookup_type = self.lookup_type
        value = self.value
        contact_types = split_csv(self.people_contact_types) or ["email-work"]

        if self.query and not value:
            try:
                params = json.loads(self.query)
                lookup_type = params.get("lookup_type", lookup_type)
                value = params.get("value", "")
                if params.get("people_contact_types"):
                    contact_types = split_csv(params["people_contact_types"]) or contact_types
            except (json.JSONDecodeError, TypeError):
                value = self.query

        result = pubrio_post(self.api_key, "/redeem/people", {
            lookup_type: value,
            "people_contact_types": contact_types,
        })
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
