from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioTimelinesAIAPIComponent(ComposioBaseComponent):
    display_name: str = "TimelinesAI"
    icon = "Timelinesai"
    documentation: str = "https://docs.composio.dev"
    app_name = "timelinesai"

    def set_default_tools(self):
        """Set the default tools for TimelinesAI component."""
