from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioOutlookAPIComponent(ComposioBaseComponent):
    component_id: str = "7ee06f42-e0bf-43a6-9051-b86f7db8c54c"
    display_name: str = "Outlook"
    icon = "Outlook"
    documentation: str = "https://docs.composio.dev"
    app_name = "outlook"

    def set_default_tools(self):
        """Set the default tools for Gmail component."""
