"""Pin tool_calling defaults for image-output models in the static catalogs.

The Agent picker filters on ``tool_calling=True``. Image-generation models
(outputs include ``image``) can't run with tools per the upstream APIs and
must not pass through that filter. Earlier revisions of the Google catalog
defaulted these models to ``tool_calling=True``, which leaked
``gemini-3.1-flash-image-preview`` into the Agent dropdown.

This file pins the correct flag on the known image models and exposes a
generic check that flags any future image-output model defaulted incorrectly
when added to a static ``*_constants.py`` list.
"""

from __future__ import annotations

import pytest

GOOGLE_IMAGE_MODELS = (
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-preview-image-generation",
    "gemini-3-pro-image-preview",
    "gemini-3.1-flash-image-preview",
)


@pytest.mark.parametrize("model_name", GOOGLE_IMAGE_MODELS)
def test_google_image_models_have_tool_calling_disabled(model_name: str):
    """Known Google image-output models declare tool_calling=False.

    The Agent picker filters on ``tool_calling=True``; image-generation
    models can't run with tools per Google's API and must not leak through
    the filter before the models.dev override hydrates.
    """
    from lfx.base.models.google_generative_ai_constants import (
        GOOGLE_GENERATIVE_AI_MODELS_DETAILED,
    )

    by_name = {m["name"]: m for m in GOOGLE_GENERATIVE_AI_MODELS_DETAILED}
    assert model_name in by_name, (
        f"{model_name} should remain in the static Google catalog so the static-only "
        "fallback retains its tool_calling=False curation; remove this test entry if "
        "the upstream model is intentionally dropped."
    )
    assert by_name[model_name].get("tool_calling") is False, (
        f"{model_name} is an image-output model and must declare tool_calling=False; "
        "the Agent picker filters on tool_calling=True and would otherwise surface it."
    )


def test_no_google_model_with_image_in_name_defaults_to_tool_calling_true():
    """Heuristic regression guard catches future image-in-name offenders.

    If a model legitimately breaks the convention (e.g. a future
    ``gemini-Nx-image`` that does support tool calling), extend the
    ``allowlist`` below with a justification.
    """
    from lfx.base.models.google_generative_ai_constants import (
        GOOGLE_GENERATIVE_AI_MODELS_DETAILED,
    )

    allowlist: set[str] = set()
    suspects = [
        m for m in GOOGLE_GENERATIVE_AI_MODELS_DETAILED if "image" in m["name"].lower() and m["name"] not in allowlist
    ]
    offenders = [m["name"] for m in suspects if m.get("tool_calling")]
    assert offenders == [], (
        f"Image-output Google models with tool_calling=True (will leak into Agent picker): {offenders}"
    )
