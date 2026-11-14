from lfx.base.models.anthropic_constants import (
    ANTHROPIC_MODELS,
    ANTHROPIC_MODELS_DETAILED,
    DEPRECATED_MODELS,
)

# Retired by Anthropic on the dates in
# https://platform.claude.com/docs/en/about-claude/model-deprecations
RETIRED_MODELS = [
    "claude-sonnet-4-20250514",  # 2026-06-15
    "claude-opus-4-20250514",  # 2026-06-15
    "claude-opus-4-1-20250805",  # 2026-08-05
    "claude-3-haiku-20240307",  # 2026-04-20
]


def test_retired_models_are_not_offered():
    for name in RETIRED_MODELS:
        assert name not in ANTHROPIC_MODELS, f"{name} is retired but still selectable"


def test_retired_models_stay_known_as_deprecated():
    # A saved flow that names a retired model must still resolve to its metadata.
    names = {metadata["name"] for metadata in ANTHROPIC_MODELS_DETAILED}
    for name in RETIRED_MODELS:
        assert name in names
        assert name in DEPRECATED_MODELS
