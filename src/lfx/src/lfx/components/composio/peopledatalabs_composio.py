from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioPeopleDataLabsAPIComponent(ComposioBaseComponent):
    component_id: str = "72a14d9f-4d07-487b-939f-ff4e2bb0d600"
    display_name: str = "PeopleDataLabs"
    icon = "Peopledatalabs"
    documentation: str = "https://docs.composio.dev"
    app_name = "peopledatalabs"

    def set_default_tools(self):
        """Set the default tools for PeopleDataLabs component."""
