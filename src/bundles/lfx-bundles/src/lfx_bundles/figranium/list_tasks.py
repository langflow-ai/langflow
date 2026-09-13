from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from .base import FigraniumAPIClient, secret_value


class FigraniumListTasksComponent(Component):
    display_name = "List Figranium Tasks"
    description = "List saved Figranium browser automation tasks through the HTTP API."
    documentation = "https://docs.figranium.dev"
    icon = "List"
    name = "FigraniumListTasks"

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

    outputs = [Output(display_name="Tasks", name="tasks", type_=list[Data], method="list_tasks")]

    def list_tasks(self) -> list[Data]:
        client = FigraniumAPIClient(self.base_url, secret_value(self.api_key))
        result = client.request("GET", "/api/tasks/list")
        tasks = result.get("tasks", []) if isinstance(result, dict) else []
        data = [Data(data=task) for task in tasks if isinstance(task, dict)]
        self.status = data
        return data
