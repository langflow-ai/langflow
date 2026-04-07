import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post, split_csv


class PubrioBatchRedeemContactsComponent(Component):
    display_name = "Pubrio Batch Redeem Contacts"
    description = "Batch reveal contacts for multiple people at once (uses credits)."
    icon = "mail"
    name = "PubrioBatchRedeemContacts"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(
            name="query", display_name="Query", info="JSON with peoples and people_contact_types.", tool_mode=True
        ),
        MessageTextInput(name="peoples", display_name="People UUIDs", info="Comma-separated people_search_id UUIDs."),
        MessageTextInput(
            name="people_contact_types",
            display_name="Contact Types",
            info="Comma-separated: email-work, email-personal, phone",
            value="email-work",
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="batch_redeem"),
    ]

    def batch_redeem(self) -> DataFrame:
        peoples = split_csv(self.peoples) or []
        contact_types = split_csv(self.people_contact_types) or ["email-work"]

        if self.query and not peoples:
            try:
                params = json.loads(self.query)
                if not isinstance(params, dict):
                    raise TypeError
                peoples = split_csv(params.get("peoples", "")) or []
                if params.get("people_contact_types"):
                    contact_types = split_csv(params["people_contact_types"]) or contact_types
            except (json.JSONDecodeError, TypeError):
                pass

        result = pubrio_post(
            self.api_key,
            "/redeem/people/batch",
            {
                "peoples": peoples,
                "people_contact_types": contact_types,
            },
        )
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
