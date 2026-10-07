"""Every curated assistant preference must be a model the provider actually offers.

LE-2310: ``ASSISTANT_PREFERRED_MODELS["Google Generative AI"]`` listed two
models, and the second (``gemini-1.5-pro``) is flagged ``deprecated`` in the
catalog. ``_catalog_model_names`` filters deprecated models out, so that entry
could never be selected — the list looked like it had a fallback and did not.

The fallback the assistant walks at runtime is
``get_provider_model_candidates``. It starts with the default and then follows
catalog order, which puts small flash SKUs ahead of the provider's other
pro-class models. When the default is unusable the assistant should drop to the
next curated preference, not to the first name that happens to be next in the
catalog.
"""

import pytest
from langflow.agentic.services.provider_service import (
    ASSISTANT_PREFERRED_MODELS,
    _catalog_model_names,
    get_provider_model_candidates,
)
from lfx.base.models.model_metadata import LIVE_MODEL_PROVIDERS

# Live providers resolve their real list per user at request time, so a static
# catalog check would be a false negative for them.
STATIC_CATALOG_PROVIDERS = [p for p in ASSISTANT_PREFERRED_MODELS if p not in LIVE_MODEL_PROVIDERS]


@pytest.mark.parametrize("provider", STATIC_CATALOG_PROVIDERS)
def test_should_offer_every_preferred_model_when_provider_uses_static_catalog(provider):
    offered = set(_catalog_model_names(provider))

    unreachable = [name for name in ASSISTANT_PREFERRED_MODELS[provider] if name not in offered]

    assert not unreachable, (
        f"{provider} prefers {unreachable}, which the catalog does not offer "
        "(missing or deprecated), so those entries can never be selected"
    )


def test_should_try_remaining_preferred_models_before_other_catalog_models():
    provider = "Google Generative AI"
    candidates = get_provider_model_candidates(provider)
    preferred = [name for name in ASSISTANT_PREFERRED_MODELS[provider] if name in candidates]

    assert len(preferred) > 1, "test needs a provider with more than one reachable preference"

    first_non_preferred = next(i for i, name in enumerate(candidates) if name not in preferred)
    last_preferred = max(candidates.index(name) for name in preferred)

    assert last_preferred < first_non_preferred, (
        f"fallback order {candidates[:6]} puts a non-preferred model ahead of "
        f"preferred {preferred}, so a blocked default drops to a weaker model than it should"
    )
