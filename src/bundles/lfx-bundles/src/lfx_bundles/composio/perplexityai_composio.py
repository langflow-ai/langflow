from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioPerplexityAIAPIComponent(ComposioBaseComponent):
    display_name: str = "PerplexityAI"
    icon = "PerplexityComposio"
    documentation: str = "https://docs.composio.dev"
    app_name = "perplexityai"

    def set_default_tools(self):
        """Set the default tools for PerplexityAI component."""
