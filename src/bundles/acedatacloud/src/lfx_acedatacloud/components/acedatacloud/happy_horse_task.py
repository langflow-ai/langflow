"""Happy Horse task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class HappyHorseRetrieveTaskComponent(AceTaskComponent):
    display_name = "Happy Horse Retrieve Task by Ace Data Cloud"
    description = "Query the same Happy Horse task through Ace Data Cloud without another paid generation."
    icon = "Clapperboard"
    documentation = "https://docs.langflow.org/acedatacloud-happy-horse"
    service_name = "happy_horse"
    inputs = task_inputs("happy_horse")
