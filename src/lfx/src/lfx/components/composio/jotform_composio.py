from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioJotformAPIComponent(ComposioBaseComponent):
    component_id: str = "6a81ee5a-877c-4793-8743-72d1958d6ee3"
    display_name: str = "Jotform"
    icon = "Jotform"
    documentation: str = "https://docs.composio.dev"
    app_name = "jotform"

    def set_default_tools(self):
        """Set the default tools for Jotform component."""
