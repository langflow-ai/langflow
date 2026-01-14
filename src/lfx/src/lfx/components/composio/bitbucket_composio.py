from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioBitbucketAPIComponent(ComposioBaseComponent):
    component_id: str = "9d1736ae-98a2-42ac-b700-1e538c477bbf"
    display_name: str = "Bitbucket"
    icon = "Bitbucket"
    documentation: str = "https://docs.composio.dev"
    app_name = "bitbucket"

    def set_default_tools(self):
        """Set the default tools for Bitbucket component."""
