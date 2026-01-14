from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFinageAPIComponent(ComposioBaseComponent):
    component_id: str = "53d1de1e-c45d-4c91-800b-acf46f694318"
    display_name: str = "Finage"
    icon = "Finage"
    documentation: str = "https://docs.composio.dev"
    app_name = "finage"

    def set_default_tools(self):
        """Set the default tools for Finage component."""
