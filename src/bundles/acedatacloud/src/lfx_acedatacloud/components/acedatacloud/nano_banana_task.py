"""Nano Banana task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class NanoBananaRetrieveTaskComponent(AceTaskComponent):
    display_name = "Nano Banana Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "nano_banana"
    inputs = task_inputs("nano_banana")
