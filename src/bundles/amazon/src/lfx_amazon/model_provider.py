"""Static unified model catalog for Amazon Bedrock."""

from lfx.base.models.model_metadata import create_model_metadata

_PROVIDER = "Amazon Bedrock"
_ICON = "Amazon"

EU_BEDROCK_INFERENCE_PROFILE_IDS: tuple[str, ...] = (
    "eu.anthropic.claude-opus-4-8",
    "eu.anthropic.claude-sonnet-5",
    "eu.anthropic.claude-opus-4-7",
    "eu.anthropic.claude-sonnet-4-6",
    "eu.anthropic.claude-opus-4-6-v1",
    "eu.anthropic.claude-opus-4-5-20251101-v1:0",
    "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
    "eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "eu.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "eu.anthropic.claude-3-haiku-20240307-v1:0",
    "eu.amazon.nova-2-lite-v1:0",
    "eu.amazon.nova-pro-v1:0",
    "eu.amazon.nova-lite-v1:0",
    "eu.amazon.nova-micro-v1:0",
    "eu.meta.llama3-2-3b-instruct-v1:0",
    "eu.meta.llama3-2-1b-instruct-v1:0",
)

_REASONING_MODELS = frozenset(EU_BEDROCK_INFERENCE_PROFILE_IDS[:5])
_MODELS_WITHOUT_TOOL_CALLING = frozenset(EU_BEDROCK_INFERENCE_PROFILE_IDS[-2:])


def load_bedrock_models() -> list[dict]:
    """Return the hardcoded EU Bedrock inference-profile catalog."""
    return [
        create_model_metadata(
            provider=_PROVIDER,
            name=model_id,
            icon=_ICON,
            tool_calling=model_id not in _MODELS_WITHOUT_TOOL_CALLING,
            reasoning=model_id in _REASONING_MODELS,
        )
        for model_id in EU_BEDROCK_INFERENCE_PROFILE_IDS
    ]
