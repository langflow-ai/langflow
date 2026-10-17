"""Nano Banana task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class NanoBananaRetrieveTaskComponent(AceTaskComponent):
    display_name = "Nano Banana Retrieve Task by Ace Data Cloud"
    description = "Query the same Nano Banana task through Ace Data Cloud without another paid generation."
    icon = "Image"
    documentation = "https://docs.langflow.org/acedatacloud-nano-banana"
    service_name = "nano_banana"
    inputs = task_inputs("nano_banana")
