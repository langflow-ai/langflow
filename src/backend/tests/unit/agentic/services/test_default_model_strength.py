"""The assistant's default model must be the provider's BEST agent model.

QA: the default the assistant picks arrives with the composer's own
"may underperform on agent tasks" warning already showing — the out-of-the-box
experience should be great without the user changing anything.

Root cause: ``get_default_model`` returned the provider catalog's first entry
(the catalog sorts by ``created``, which is 0 for every model, so the order is
just the hand-written list order). "First in the list" is not "best": Google's
first entry is ``gemini-2.5-flash``, a small SKU the UI flags as weak.
"""

import re

import pytest
from langflow.agentic.services.provider_service import ASSISTANT_PREFERRED_MODELS, get_default_model

# Mirrors src/frontend/src/components/core/assistantPanel/helpers/model-strength.ts —
# the classifier that drives the composer's warning. A default that trips this is the bug.
_WEAK_SUFFIX = re.compile(r"\b(nano|mini|micro|tiny|small|lite|instant|flash|haiku)\b", re.IGNORECASE)
_WEAK_FAMILY = re.compile(r"\bgpt-3(\.5)?\b|\bclaude-instant\b|\bgemini-1\.0\b|\bphi-?[1-3]\b", re.IGNORECASE)
_SMALL_PARAM = re.compile(r"(?<![\d])([1-9]|1[0-3])b\b", re.IGNORECASE)
_LARGE_PARAM = re.compile(r"(?<![\d.])(1[4-9]|[2-9]\d|\d{3,})b\b", re.IGNORECASE)

_CATALOG_PROVIDERS = ["OpenAI", "Anthropic", "Google Generative AI", "Azure AI Foundry"]


def _is_weak_agent_model(name: str | None) -> bool:
    if not name:
        return False
    if _LARGE_PARAM.search(name):
        return False
    return bool(_WEAK_SUFFIX.search(name) or _WEAK_FAMILY.search(name) or _SMALL_PARAM.search(name))


@pytest.mark.parametrize("provider", _CATALOG_PROVIDERS)
def test_default_model_is_not_flagged_weak_by_the_composer(provider):
    """No provider may default to a model the composer warns about."""
    default = get_default_model(provider)
    assert default, f"{provider} has no default model"
    assert not _is_weak_agent_model(default), (
        f"{provider} defaults to {default!r}, which the composer flags as "
        "'may underperform on agent tasks' — the default must be the best agent model."
    )


def test_google_defaults_to_pro_not_flash():
    """Regression pin for the reported case: Google's catalog lists flash first."""
    assert get_default_model("Google Generative AI") == "gemini-2.5-pro"


@pytest.mark.parametrize("provider", _CATALOG_PROVIDERS)
def test_preferred_models_exist_in_the_catalog(provider):
    """A curated preference that no longer exists would silently fall back."""
    from lfx.base.models.unified_models import get_unified_models_detailed

    detailed = get_unified_models_detailed(
        providers=[provider], include_unsupported=False, include_deprecated=False, model_type="llm"
    )
    catalog = {m.get("model_name") for pd in detailed for m in pd.get("models", [])}
    preferred = ASSISTANT_PREFERRED_MODELS.get(provider, ())
    assert preferred, f"{provider} must declare an assistant preference"
    assert any(name in catalog for name in preferred), (
        f"none of {provider}'s preferred models {preferred} exist in the catalog {sorted(catalog)[:8]}…"
    )


def test_provider_without_a_curated_preference_keeps_the_catalog_default():
    """The preference map is an override, not a gate: unlisted providers still resolve."""
    assert "Groq" not in ASSISTANT_PREFERRED_MODELS
    assert get_default_model("Ollama") == "llama3.3"


def test_unknown_provider_resolves_to_nothing():
    assert get_default_model("NotARealProvider") is None
