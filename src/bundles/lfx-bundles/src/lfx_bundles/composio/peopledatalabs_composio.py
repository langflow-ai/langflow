from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioPeopleDataLabsAPIComponent(ComposioBaseComponent):
    display_name: str = "PeopleDataLabs"
    icon = "Peopledatalabs"
    documentation: str = "https://docs.composio.dev"
    app_name = "peopledatalabs"

    def set_default_tools(self):
        """Set the default tools for PeopleDataLabs component."""
