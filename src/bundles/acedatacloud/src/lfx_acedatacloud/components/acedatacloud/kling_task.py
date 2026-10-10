"""Kling task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class KlingRetrieveTaskComponent(AceTaskComponent):
    display_name = "Kling Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "kling"
    inputs = task_inputs("kling")
