from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioYoutubeAPIComponent(ComposioBaseComponent):
    component_id: str = "30e2e0ab-8760-43c9-ad2b-8134a7625490"
    display_name: str = "YouTube"
    icon = "YouTube"
    documentation: str = "https://docs.composio.dev"
    app_name = "youtube"

    def set_default_tools(self):
        """Set the default tools for Youtube component."""
