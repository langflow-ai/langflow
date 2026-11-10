"""List the saved tasks on a Figranium instance."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from lfx_bundles.figranium.base import API_KEY_INFO, BASE_URL_INFO, DOCUMENTATION_URL, FigraniumAPIClient, extract_items


class FigraniumListTasksComponent(Component):
    """List saved Figranium tasks as one ``Data`` per task."""

    display_name = "List Figranium Tasks"
    description = "List the saved browser automation tasks on a Figranium instance."
    documentation = DOCUMENTATION_URL
    icon = "Figranium"
    name = "FigraniumListTasks"

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

    outputs = [Output(display_name="Tasks", name="tasks", type_=list[Data], method="list_tasks")]

    def list_tasks(self) -> list[Data]:
        """GET the task summaries (id, name, description) from Figranium."""
        client = FigraniumAPIClient(self.base_url, self.api_key)
        data = [Data(data=task) for task in extract_items(client.get("/api/tasks/list"), "tasks")]
        self.status = data
        return data
