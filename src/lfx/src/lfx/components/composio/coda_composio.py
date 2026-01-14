from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioCodaAPIComponent(ComposioBaseComponent):
    component_id: str = "dea650c4-5f3c-48cc-a3f0-1e4ec9d53266"
    display_name: str = "Coda"
    icon = "Coda"
    documentation: str = "https://docs.composio.dev"
    app_name = "coda"

    def set_default_tools(self):
        """Set the default tools for Coda component."""
