from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFixerAPIComponent(ComposioBaseComponent):
    component_id: str = "53411b3b-3dca-48c2-b1a6-7bbcdc735904"
    display_name: str = "Fixer"
    icon = "Fixer"
    documentation: str = "https://docs.composio.dev"
    app_name = "fixer"

    def set_default_tools(self):
        """Set the default tools for Fixer component."""
