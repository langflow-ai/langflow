from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioCalendlyAPIComponent(ComposioBaseComponent):
    display_name: str = "Calendly"
    icon = "Calendly"
    documentation: str = "https://docs.composio.dev"
    app_name = "calendly"

    def set_default_tools(self):
        """Set the default tools for Calendly component."""
