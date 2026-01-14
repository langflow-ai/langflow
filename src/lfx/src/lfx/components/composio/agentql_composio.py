from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioAgentQLAPIComponent(ComposioBaseComponent):
    component_id: str = "4b1617ac-d005-4405-94fa-f6ba2e873ae4"
    display_name: str = "AgentQL"
    icon = "AgentQL"
    documentation: str = "https://docs.composio.dev"
    app_name = "agentql"

    def set_default_tools(self):
        """Set the default tools for AgentQL component."""
