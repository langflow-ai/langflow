from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioTwitterAPIComponent(ComposioBaseComponent):
    display_name: str = "Twitter"
    icon = "TwitterX"
    documentation: str = "https://docs.composio.dev"
    app_name = "twitter"

    def set_default_tools(self):
        """Set the default tools for Twitter component."""