from lfx_composio.base.composio_base import ComposioBaseComponent


class ComposioAgentQLAPIComponent(ComposioBaseComponent):
    display_name: str = "AgentQL"
    icon = "AgentQL"
    documentation: str = "https://docs.composio.dev"
    app_name = "agentql"

    def set_default_tools(self):
        """Set the default tools for AgentQL component."""
