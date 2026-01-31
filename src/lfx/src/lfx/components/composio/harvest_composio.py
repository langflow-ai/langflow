from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioHarvestAPIComponent(ComposioBaseComponent):
    display_name: str = "Harvest"
    icon = "Harvest"
    documentation: str = "https://docs.composio.dev"
    app_name = "harvest"

    def set_default_tools(self):
        """Set the default tools for Harvest component."""
