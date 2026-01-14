from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioJiraAPIComponent(ComposioBaseComponent):
    component_id: str = "f4405be5-6f87-4fee-b3c7-36cbee8132c5"
    display_name: str = "Jira"
    icon = "Jira"
    documentation: str = "https://docs.composio.dev"
    app_name = "jira"

    def set_default_tools(self):
        """Set the default tools for Jira component."""
