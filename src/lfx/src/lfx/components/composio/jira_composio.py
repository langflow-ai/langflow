from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioJiraAPIComponent(ComposioBaseComponent):
    display_name: str = "Jira"
    icon = "Jira"
    documentation: str = "https://docs.composio.dev"
    app_name = "jira"

    def set_default_tools(self):
        """Set the default tools for Jira component."""
