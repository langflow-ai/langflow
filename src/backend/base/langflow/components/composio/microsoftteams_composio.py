from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioMicrosoftTeamsAPIComponent(ComposioBaseComponent):
    display_name: str = "Microsoft Teams"
    icon = "MicrosoftTeams"
    documentation: str = "https://docs.composio.dev"
    app_name = "microsoftteams"

    def set_default_tools(self):
        """Set the default tools for Microsoft Teams component."""
