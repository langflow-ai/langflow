from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioBitbucketAPIComponent(ComposioBaseComponent):
    display_name: str = "Bitbucket"
    icon = "Bitbucket"
    documentation: str = "https://docs.composio.dev"
    app_name = "bitbucket"

    def set_default_tools(self):
        """Set the default tools for Bitbucket component."""
