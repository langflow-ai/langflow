"""Static unified model catalog for Amazon Bedrock."""

from lfx.base.models.model_metadata import create_model_metadata

_PROVIDER = "Amazon Bedrock"
_ICON = "Amazon"

# EU system-defined cross-region inference profile IDs supported by this
# provider. Keep the exact AWS IDs here: unlike foundation model IDs, these
# include the geographic ``eu.`` routing prefix.
EU_BEDROCK_INFERENCE_PROFILE_IDS: tuple[str, ...] = (
    # Anthropic Claude
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
    # NOTE: eu.anthropic.claude-3-5-haiku-20241022-v1:0 is intentionally
    # omitted. AWS lists its end-of-life as 2026-06-19, so it must not be
    # advertised as an active/default model. See
    # test_expired_claude_3_5_haiku_profile_is_not_advertised.
    "eu.anthropic.claude-3-haiku-20240307-v1:0",
    # Amazon Nova
    "eu.amazon.nova-2-lite-v1:0",
    "eu.amazon.nova-pro-v1:0",
    "eu.amazon.nova-lite-v1:0",
    "eu.amazon.nova-micro-v1:0",
    # Meta Llama (EU profiles are currently limited to these legacy models)
    "eu.meta.llama3-2-3b-instruct-v1:0",
    "eu.meta.llama3-2-1b-instruct-v1:0",
)

_MODELS_WITHOUT_TOOL_CALLING = frozenset(
    {
        "eu.meta.llama3-2-3b-instruct-v1:0",
        "eu.meta.llama3-2-1b-instruct-v1:0",
    }
)

# Explicit per-model reasoning metadata. Only the current Claude 4.6+/5
# inference profiles expose extended reasoning; legacy Claude 3.x/4.5 profiles
# do not. This mirrors the reasoning flags declared for the globally routable
# profiles in ``lfx.base.models.aws_constants.AWS_MODELS_DETAILED`` — keep the
# two in sync. A substring check on ``anthropic.claude`` would incorrectly flag
# legacy profiles (e.g. claude-3-7-sonnet) as reasoning models.
_REASONING_MODELS = frozenset(
    {
        "eu.anthropic.claude-opus-4-8",
        "eu.anthropic.claude-sonnet-5",
        "eu.anthropic.claude-opus-4-7",
        "eu.anthropic.claude-sonnet-4-6",
        "eu.anthropic.claude-opus-4-6-v1",
    }
)


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
