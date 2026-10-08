"""Veo task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class VeoRetrieveTaskComponent(AceTaskComponent):
    display_name = "Veo Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "veo"
    inputs = task_inputs("veo")
