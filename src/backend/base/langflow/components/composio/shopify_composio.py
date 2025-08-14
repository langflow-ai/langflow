from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioShopifyAPIComponent(ComposioBaseComponent):
    display_name: str = "Shopify"
    icon = "Shopify"
    documentation: str = "https://docs.composio.dev"
    app_name = "shopify"

    def set_default_tools(self):
        """Set the default tools for Shopify component."""
