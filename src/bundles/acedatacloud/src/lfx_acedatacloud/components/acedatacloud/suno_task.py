"""Suno task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class SunoRetrieveTaskComponent(AceTaskComponent):
    display_name = "Suno Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "suno"
    inputs = task_inputs("suno")
