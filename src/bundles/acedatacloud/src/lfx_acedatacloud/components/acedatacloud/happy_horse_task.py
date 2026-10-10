"""Happy Horse task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class HappyHorseRetrieveTaskComponent(AceTaskComponent):
    display_name = "Happy Horse Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "happy_horse"
    inputs = task_inputs("happy_horse")
