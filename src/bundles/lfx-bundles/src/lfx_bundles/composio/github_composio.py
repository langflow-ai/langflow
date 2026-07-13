from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGitHubAPIComponent(ComposioBaseComponent):
    display_name: str = "GitHub"
    icon = "GithubComposio"
    documentation: str = "https://docs.composio.dev"
    app_name = "github"

    def set_default_tools(self):
        """Set the default tools for GitHub component."""
