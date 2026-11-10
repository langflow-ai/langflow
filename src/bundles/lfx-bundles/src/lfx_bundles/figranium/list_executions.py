"""List the execution history of a Figranium instance."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from lfx_bundles.figranium.base import API_KEY_INFO, BASE_URL_INFO, DOCUMENTATION_URL, FigraniumAPIClient, extract_items


class FigraniumListExecutionsComponent(Component):
    """List Figranium executions as one ``Data`` per execution."""

    display_name = "List Figranium Executions"
    description = "List the execution history of a Figranium instance."
    documentation = DOCUMENTATION_URL
    icon = "Figranium"
    name = "FigraniumListExecutions"

    inputs = [
        StrInput(
            name="base_url",
            display_name="Figranium URL",
            info=BASE_URL_INFO,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info=API_KEY_INFO,
            required=True,
            password=True,
        ),
    ]

    outputs = [Output(display_name="Executions", name="executions", type_=list[Data], method="list_executions")]

    def list_executions(self) -> list[Data]:
        """GET the execution summaries from Figranium."""
        client = FigraniumAPIClient(self.base_url, self.api_key)
        data = [Data(data=item) for item in extract_items(client.get("/api/executions/list"), "executions")]
        self.status = data
        return data
