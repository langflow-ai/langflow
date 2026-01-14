from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioPandadocAPIComponent(ComposioBaseComponent):
    component_id: str = "4ce90514-6668-4c76-9c1d-d82fc9fb039f"
    display_name: str = "Pandadoc"
    icon = "Pandadoc"
    documentation: str = "https://docs.composio.dev"
    app_name = "pandadoc"

    def set_default_tools(self):
        """Set the default tools for Pandadoc component."""
