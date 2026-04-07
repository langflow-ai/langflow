import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post


class PubrioValidateWebhookComponent(Component):
    display_name = "Pubrio Validate Webhook"
    description = "Validate a webhook destination URL."
    icon = "activity"
    name = "PubrioValidateWebhook"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(name="webhook_url", display_name="Webhook URL", info="Webhook URL to validate.", required=True, tool_mode=True),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run"),
    ]

    def run(self) -> DataFrame:
        result = pubrio_post(self.api_key, "/monitors/webhook/validate", {"webhook_url": self.webhook_url})
        data = [Data(text=json.dumps(result), data=result if isinstance(result, dict) else {"result": result})]
        self.status = data
        return DataFrame(data)
