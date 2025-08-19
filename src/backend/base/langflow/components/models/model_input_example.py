from langflow.custom.custom_component.component import Component
from langflow.field_typing import LanguageModel
from langflow.inputs.inputs import ModelInput, SecretStrInput
from langflow.template.field.base import Output


class ModelInputExampleComponent(Component):
    """Example component showing how to use ModelInput with API key management."""

    display_name = "Model Input Example"
    description = "Example component demonstrating ModelInput with API key fields."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"

    inputs = [
        ModelInput(
            name="model_selection",
            required=True,
            display_name="Model",
            model_type="language",
            placeholder="Select a model",
            temperature=0.7,
            max_tokens=1000,
        ),
        SecretStrInput(
            name="api_key",
            display_name="OpenAI API Key",
            info="OpenAI API Key for OpenAI models",
            value="OPENAI_API_KEY",
        ),
    ]

    outputs = [
        Output(display_name="Language Model", name="model_output", method="build_model"),
    ]

    def build_model(self) -> LanguageModel:
        """Build and return the language model using ModelInput with API keys."""
        # Now it's super simple! self.model_selection is automatically the ModelInput object
        model = self.model_selection.build_model(api_key=self.api_key)

        if not model:
            # Parse the selection to show a helpful error message
            selection_value = ""
            if self.model_selection.value and isinstance(self.model_selection.value, list):
                first_item = self.model_selection.value[0]
                selection_value = first_item.get("name", "") if isinstance(first_item, dict) else str(first_item)
            if ":" in selection_value:
                provider, model_name = selection_value.split(":", 1)
                msg = f"Failed to build {provider} model '{model_name}'. Check API key configuration."
            else:
                msg = "Failed to build model. Invalid selection format."
            raise ValueError(msg)

        return model
