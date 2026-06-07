from .model_metadata import create_model_metadata

AZURE_OPENAI_MODELS_DETAILED = [
    create_model_metadata(provider="Azure OpenAI", name="gpt-4o", icon="Azure", tool_calling=True, default=True),
    create_model_metadata(provider="Azure OpenAI", name="gpt-4o-mini", icon="Azure", tool_calling=True),
    create_model_metadata(provider="Azure OpenAI", name="gpt-4-turbo", icon="Azure", tool_calling=True),
    create_model_metadata(provider="Azure OpenAI", name="gpt-4", icon="Azure", tool_calling=True),
    create_model_metadata(provider="Azure OpenAI", name="gpt-35-turbo", icon="Azure", tool_calling=True),
]
