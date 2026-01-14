from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioMissiveAPIComponent(ComposioBaseComponent):
    component_id: str = "ee979797-dd7c-4202-8560-7ff663ab9d37"
    display_name: str = "Missive"
    icon = "Missive"
    documentation: str = "https://docs.composio.dev"
    app_name = "missive"

    def set_default_tools(self):
        """Set the default tools for Missive component."""
