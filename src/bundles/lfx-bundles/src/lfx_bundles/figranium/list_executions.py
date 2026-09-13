from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from .base import FigraniumAPIClient, secret_value


class FigraniumListExecutionsComponent(Component):
    display_name = "List Figranium Executions"
    description = "List Figranium execution history through the HTTP API."
    documentation = "https://docs.figranium.dev"
    icon = "History"
    name = "FigraniumListExecutions"

    inputs = [
        StrInput(
            name="base_url",
            display_name="Figranium URL",
            info="Base URL of your Figranium instance, for example https://figranium.example.com.",
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Figranium API key sent as the x-api-key header.",
            required=True,
            password=True,
        ),
    ]

    outputs = [Output(display_name="Executions", name="executions", type_=list[Data], method="list_executions")]

    def list_executions(self) -> list[Data]:
        client = FigraniumAPIClient(self.base_url, secret_value(self.api_key))
        result = client.request("GET", "/api/executions/list")
        executions = result.get("executions", []) if isinstance(result, dict) else []
        data = [Data(data=item) for item in executions if isinstance(item, dict)]
        self.status = data
        return data
