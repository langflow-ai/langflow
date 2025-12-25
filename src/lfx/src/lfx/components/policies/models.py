"""
details of the models supported for the buildtime step
"""

BUILDTIME_MODELS = [
    {
        "name": "gpt-4o",
        "icon": "OpenAI",
        "category": "OpenAI",
        "provider": "OpenAI",
        "metadata": {
            "context_length": 128000,
            "model_class": "ChatOpenAI",
            "model_name_param": "model",
            "api_key_param": "api_key",
            "reasoning_models": ["gpt-4o"]
        }
    },
    {
        "name": "claude-sonnet-4",
        "icon": "Anthropic",
        "category": "Anthropic",
        "provider": "Anthropic",
        "metadata": {
            "context_length": 128000,
            "model_class": "ChatAnthropic",
            "model_name_param": "model",
            "api_key_param": "api_key"
        }
    }
]
