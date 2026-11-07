"""Fish Audio task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class FishAudioRetrieveTaskComponent(AceTaskComponent):
    display_name = "Fish Audio Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "fish_audio"
    inputs = task_inputs("fish_audio")
