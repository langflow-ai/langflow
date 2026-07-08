from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioBrightdataAPIComponent(ComposioBaseComponent):
    display_name: str = "Brightdata"
    icon = "Brightdata"
    documentation: str = "https://docs.composio.dev"
    app_name = "brightdata"

    def set_default_tools(self):
        """Set the default tools for Brightdata component."""
