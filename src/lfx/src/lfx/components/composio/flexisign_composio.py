from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFlexisignAPIComponent(ComposioBaseComponent):
    component_id: str = "240f86e8-e9c4-4d09-805f-06c1f012f35d"
    display_name: str = "Flexisign"
    icon = "Flexisign"
    documentation: str = "https://docs.composio.dev"
    app_name = "flexisign"

    def set_default_tools(self):
        """Set the default tools for Flexisign component."""
