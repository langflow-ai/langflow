from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioTimelinesAIAPIComponent(ComposioBaseComponent):
    component_id: str = "1534ae4b-6ba9-4d0a-9810-fd52554c1da8"
    display_name: str = "TimelinesAI"
    icon = "Timelinesai"
    documentation: str = "https://docs.composio.dev"
    app_name = "timelinesai"

    def set_default_tools(self):
        """Set the default tools for TimelinesAI component."""
