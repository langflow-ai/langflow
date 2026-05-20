"""Shared model configuration for agentic flows."""

MODEL_CLASSES = {
    "OpenAI": "ChatOpenAI",
    "Anthropic": "ChatAnthropic",
    "Google Generative AI": "ChatGoogleGenerativeAI",
    "Groq": "ChatGroq",
    "Azure OpenAI": "AzureChatOpenAI",
}


def build_model_config(provider: str, model_name: str) -> list[dict]:
    """Build model configuration for LanguageModelComponent."""
    return [
        {
            "icon": provider,
            "metadata": {
                "api_key_param": "api_key",  # pragma: allowlist secret
                "context_length": 128000,
                "model_class": MODEL_CLASSES.get(provider, "ChatOpenAI"),
                "model_name_param": "model",
            },
            "name": model_name,
            "provider": provider,
        }
    ]
