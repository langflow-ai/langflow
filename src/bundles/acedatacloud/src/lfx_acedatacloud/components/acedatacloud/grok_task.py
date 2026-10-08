"""Grok task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class GrokVideoRetrieveTaskComponent(AceTaskComponent):
    display_name = "Grok Video Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "grok"
    inputs = task_inputs("grok")
