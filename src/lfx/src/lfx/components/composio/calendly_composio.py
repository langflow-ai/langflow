from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioCalendlyAPIComponent(ComposioBaseComponent):
    component_id: str = "a371cc1c-3920-494d-9984-40544b4f0b72"
    display_name: str = "Calendly"
    icon = "Calendly"
    documentation: str = "https://docs.composio.dev"
    app_name = "calendly"

    def set_default_tools(self):
        """Set the default tools for Calendly component."""
