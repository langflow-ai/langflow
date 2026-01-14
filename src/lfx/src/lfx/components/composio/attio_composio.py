from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioAttioAPIComponent(ComposioBaseComponent):
    component_id: str = "7f09b067-8351-43f1-844a-7ab28b338eff"
    display_name: str = "Attio"
    icon = "Attio"
    documentation: str = "https://docs.composio.dev"
    app_name = "attio"

    def set_default_tools(self):
        """Set the default tools for Attio component."""
