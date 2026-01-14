from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioContentfulAPIComponent(ComposioBaseComponent):
    component_id: str = "0585815c-e7cf-4795-84e8-0acd7a3a4837"
    display_name: str = "Contentful"
    icon = "Contentful"
    documentation: str = "https://docs.composio.dev"
    app_name = "contentful"

    def set_default_tools(self):
        """Set the default tools for Contentful component."""
