from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioPerplexityAIAPIComponent(ComposioBaseComponent):
    component_id: str = "d40550cd-398d-49cc-8edf-631a57e9f1c7"
    display_name: str = "PerplexityAI"
    icon = "PerplexityComposio"
    documentation: str = "https://docs.composio.dev"
    app_name = "perplexityai"

    def set_default_tools(self):
        """Set the default tools for PerplexityAI component."""
