from lfx_composio.base.composio_base import ComposioBaseComponent


class ComposioFlexisignAPIComponent(ComposioBaseComponent):
    display_name: str = "Flexisign"
    icon = "Flexisign"
    documentation: str = "https://docs.composio.dev"
    app_name = "flexisign"

    def set_default_tools(self):
        """Set the default tools for Flexisign component."""
