from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioSynthFlowAIAPIComponent(ComposioBaseComponent):
    display_name: str = "SynthFlowAI"
    icon = "Synthflowai"
    documentation: str = "https://docs.composio.dev"
    app_name = "synthflow_ai"

    def set_default_tools(self):
        """Set the default tools for SynthFlowAI component."""
