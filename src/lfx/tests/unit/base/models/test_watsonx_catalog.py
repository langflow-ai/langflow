"""WatsonX seed-catalog and live-fetch metadata regressions.

The static seed list once marked every WatsonX model ``deprecated=True`` and
``fetch_live_watsonx_models`` copied that flag onto matching live results, so
the Models page showed "0 models" for IBM WatsonX before *and* after
credentials were configured — the catalog's default deprecated filter dropped
everything.
"""

from unittest.mock import patch

from lfx.base.models import model_utils
from lfx.base.models.watsonx_constants import (
    WATSONX_DEFAULT_EMBEDDING_MODELS,
    WATSONX_DEFAULT_LLM_MODELS,
)


def test_seed_catalog_offers_active_models():
    active_llms = [m for m in WATSONX_DEFAULT_LLM_MODELS if not m.get("deprecated")]
    active_embeddings = [m for m in WATSONX_DEFAULT_EMBEDDING_MODELS if not m.get("deprecated")]
    assert active_llms, "every seed LLM is deprecated: the provider renders as '0 models'"
    assert active_embeddings, "every seed embedding is deprecated: the embedding picker renders empty"


def test_fallback_names_exclude_withdrawn_models():
    withdrawn_llms = {m["name"] for m in WATSONX_DEFAULT_LLM_MODELS if m.get("deprecated")}
    assert withdrawn_llms.isdisjoint(model_utils.WATSONX_DEFAULT_LLM_MODEL_NAMES)

    withdrawn_embeddings = {m["name"] for m in WATSONX_DEFAULT_EMBEDDING_MODELS if m.get("deprecated")}
    assert withdrawn_embeddings.isdisjoint(model_utils.WATSONX_DEFAULT_EMBEDDING_MODEL_NAMES)


def _fetch_live(model_type: str, names: list[str]) -> list[dict]:
    with (
        patch.object(model_utils, "get_provider_variable_value", return_value="https://us-south.ml.cloud.ibm.com"),
        patch.object(model_utils, "get_watsonx_llm_models", return_value=names),
        patch.object(model_utils, "get_watsonx_embedding_models", return_value=names),
    ):
        return model_utils.fetch_live_watsonx_models("00000000-0000-0000-0000-000000000000", model_type)


def test_live_models_do_not_inherit_static_deprecated_flag():
    # The live query already excludes withdrawn models (!lifecycle_withdrawn):
    # whatever it returns is current, even when the static seed flags the same
    # name as deprecated (stale seed data must never hide live models).
    deprecated_seed_name = next(m["name"] for m in WATSONX_DEFAULT_LLM_MODELS if m.get("deprecated"))
    result = _fetch_live("llm", [deprecated_seed_name, "brand-new-model"])
    assert [m["deprecated"] for m in result] == [False, False]


def test_live_models_keep_static_tool_calling_flags():
    result = _fetch_live("llm", ["ibm/granite-guardian-3-8b", "unknown-model"])
    by_name = {m["name"]: m for m in result}
    assert by_name["ibm/granite-guardian-3-8b"]["tool_calling"] is False
    assert by_name["unknown-model"]["tool_calling"] is True


def test_live_embedding_models_do_not_inherit_static_deprecated_flag():
    deprecated_seed_name = next(m["name"] for m in WATSONX_DEFAULT_EMBEDDING_MODELS if m.get("deprecated"))
    result = _fetch_live("embeddings", [deprecated_seed_name])
    assert result[0]["deprecated"] is False
    assert result[0]["model_type"] == "embeddings"
