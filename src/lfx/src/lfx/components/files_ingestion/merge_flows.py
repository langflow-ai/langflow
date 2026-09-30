"""Component that merges multiple flows into a single trigger point.

Connect any number of upstream components to run them all when this component executes.
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, Output
from lfx.schema.message import Message


class MergeFlowsComponent(Component):
    display_name = "Merge Flows"
    description = "Merges multiple flows into one. Running this triggers all connected upstream flows."
    icon = "git-merge"
    name = "MergeFlows"

    inputs = [
        HandleInput(
            name="inputs",
            display_name="Inputs",
            input_types=["Data", "DataFrame", "Message", "Tool", "JSON", "Table"],
            is_list=True,
            info="Connect any upstream component outputs here. All will run when this component executes.",
        ),
    ]

    outputs = [
        Output(
            display_name="Done",
            name="done",
            method="run",
        ),
    ]

    def run(self) -> Message:
        count = len(self.inputs) if self.inputs else 0
        return Message(text=f"Merged {count} flows")
