from src.backend.base.langflow.base.models.model_constants import ModelConstants


def test_provider_names():
    # Initialize the ModelConstants
    ModelConstants.initialize()

    # Expected provider names
    expected_provider_names = [
        "AIML",
        "Amazon Bedrock",
        "Anthropic",
        "Azure OpenAI",
        "Ollama",
        "Vertex AI",
        "Cohere",
        "Google Generative AI",
        "HuggingFace",
        "OpenAI",
        "Perplexity",
        "Qianfan",
    ]

    # Assert that the provider names match the expected list
    assert expected_provider_names == ModelConstants.PROVIDER_NAMES
