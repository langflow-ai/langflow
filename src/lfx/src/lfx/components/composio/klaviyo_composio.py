from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioKlaviyoAPIComponent(ComposioBaseComponent):
    component_id: str = "9e8a8264-29fa-423e-a9e5-f10432d4fc10"
    display_name: str = "Klaviyo"
    icon = "Klaviyo"
    documentation: str = "https://docs.composio.dev"
    app_name = "klaviyo"

    def set_default_tools(self):
        """Set the default tools for Klaviyo component."""
