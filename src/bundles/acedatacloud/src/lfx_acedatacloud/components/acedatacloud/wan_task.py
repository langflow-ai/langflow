"""Wan task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class WanRetrieveTaskComponent(AceTaskComponent):
    display_name = "Wan Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "wan"
    inputs = task_inputs("wan")
