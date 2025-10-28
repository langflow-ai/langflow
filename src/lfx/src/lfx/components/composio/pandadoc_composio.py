from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioPandadocAPIComponent(ComposioBaseComponent):
    display_name: str = "Pandadoc"
    icon = "Pandadoc"
    documentation: str = "https://docs.composio.dev"
    app_name = "pandadoc"

    def set_default_tools(self):
        """Set the default tools for Pandadoc component."""
