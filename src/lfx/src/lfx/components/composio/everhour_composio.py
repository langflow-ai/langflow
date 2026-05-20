from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioEverhourAPIComponent(ComposioBaseComponent):
    display_name: str = "Everhour"
    icon = "Everhour"
    documentation: str = "https://docs.composio.dev"
    app_name = "everhour"

    def set_default_tools(self):
        """Set the default tools for Everhour component."""
