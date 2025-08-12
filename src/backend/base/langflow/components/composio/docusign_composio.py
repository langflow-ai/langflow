from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioDocusignAPIComponent(ComposioBaseComponent):
    display_name: str = "Docusign"
    icon = "Docusign"
    documentation: str = "https://docs.composio.dev"
    app_name = "docusign"

    def set_default_tools(self):
        """Set the default tools for Docusign component."""
