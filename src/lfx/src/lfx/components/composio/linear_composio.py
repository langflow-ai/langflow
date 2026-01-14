from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioLinearAPIComponent(ComposioBaseComponent):
    component_id: str = "5cb0f291-9012-4794-8221-b13813019f5a"
    display_name: str = "Linear"
    icon = "Linear"
    documentation: str = "https://docs.composio.dev"
    app_name = "linear"

    def set_default_tools(self):
        """Set the default tools for Linear component."""
