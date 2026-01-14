from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioBrightdataAPIComponent(ComposioBaseComponent):
    component_id: str = "7c32ff5c-eb3f-42eb-94fa-ecf64dcb3e44"
    display_name: str = "Brightdata"
    icon = "Brightdata"
    documentation: str = "https://docs.composio.dev"
    app_name = "brightdata"

    def set_default_tools(self):
        """Set the default tools for Brightdata component."""
