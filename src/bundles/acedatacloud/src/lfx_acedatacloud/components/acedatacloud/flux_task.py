"""Flux task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class FluxRetrieveTaskComponent(AceTaskComponent):
    display_name = "Flux Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "flux"
    inputs = task_inputs("flux")
