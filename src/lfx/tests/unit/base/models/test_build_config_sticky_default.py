"""Sticky-default behavior for ``update_model_options_in_build_config``.

Covers the declarative-filter contract introduced for issue with
``gemini-3.1-flash-image-preview`` showing up in the Agent picker:

  - ``filters`` on a ModelInput propagates through ``handle_model_input_update``
    so the dropdown only contains options that satisfy every filter.
  - The sticky-default re-injection path validates the saved selection
    against the same filters. Saved selections that don't satisfy them are
    dropped (value cleared) so the downstream auto-default picks a
    compatible row instead of silently re-injecting an unusable model.
  - Caches don't poison across different filter configurations.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


def _component(user_id: str = "u-1", inputs=None) -> SimpleNamespace:
    """Minimal component stub matching the ``update_model_options_in_build_config`` contract.

    ``inputs`` mimics the class-level ``inputs`` list on real components so
    ``_resolve_filters`` can locate the ModelInput by name.
    """
    return SimpleNamespace(user_id=user_id, cache={}, inputs=inputs or [])


def _fake_model_input(name: str = "model", filters: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(name=name, filters=filters)


def _llm_option(name: str, provider: str = "Google Generative AI") -> dict:
    return {
        "name": name,
        "provider": provider,
        "icon": provider,
        "category": provider,
        "metadata": {"model_class": "ChatGoogleGenerativeAIFixed"},
    }


# ---------------------------------------------------------------------------
# _filters_from_build_config / _augmented_cache_key_prefix
# ---------------------------------------------------------------------------


def test_filters_from_build_config_returns_declared_dict():
    from lfx.base.models.unified_models.build_config import _filters_from_build_config

    bc = {"model": {"filters": {"tool_calling": True, "reasoning": True}}}
    assert _filters_from_build_config(bc, "model") == {"tool_calling": True, "reasoning": True}


def test_filters_from_build_config_returns_empty_when_missing():
    from lfx.base.models.unified_models.build_config import _filters_from_build_config

    assert _filters_from_build_config({}, "model") == {}
    assert _filters_from_build_config({"model": {}}, "model") == {}
    assert _filters_from_build_config({"model": {"filters": None}}, "model") == {}
    assert _filters_from_build_config({"model": {"filters": "garbage"}}, "model") == {}


def test_filters_from_component_inputs_reads_class_declaration():
    """The canonical source — class-level inputs — surfaces the filters dict."""
    from lfx.base.models.unified_models.build_config import _filters_from_component_inputs

    component = _component(inputs=[_fake_model_input("model", {"tool_calling": True})])
    assert _filters_from_component_inputs(component, "model") == {"tool_calling": True}


def test_filters_from_component_inputs_empty_when_no_matching_input():
    from lfx.base.models.unified_models.build_config import _filters_from_component_inputs

    assert _filters_from_component_inputs(_component(inputs=[]), "model") == {}
    component = _component(inputs=[_fake_model_input("not_model", {"tool_calling": True})])
    assert _filters_from_component_inputs(component, "model") == {}


def test_resolve_filters_prefers_class_declaration_over_build_config():
    """Class declaration wins over stale build_config.

    Saved flows that predate the filter shipping carry no ``filters`` in
    their persisted build_config. The canonical source — the ModelInput's
    class-level declaration — must still apply, and the build_config gets
    patched in-place so the next round-trip carries the current filter.
    """
    from lfx.base.models.unified_models.build_config import _resolve_filters

    # build_config has no filters (stale saved flow).
    build_config = {"model": {"value": [], "options": []}}
    component = _component(inputs=[_fake_model_input("model", {"tool_calling": True})])
    filters = _resolve_filters(component, build_config, "model")
    assert filters == {"tool_calling": True}
    # And the build_config is patched so the next round-trip carries them.
    assert build_config["model"]["filters"] == {"tool_calling": True}


def test_resolve_filters_falls_back_to_build_config_when_component_has_no_inputs():
    """Defensive fallback for callers that don't have an inputs attribute."""
    from lfx.base.models.unified_models.build_config import _resolve_filters

    build_config = {"model": {"value": [], "options": [], "filters": {"reasoning": True}}}
    component = SimpleNamespace(user_id="u", cache={})  # no inputs attribute
    assert _resolve_filters(component, build_config, "model") == {"reasoning": True}


def test_filters_from_build_config_drops_none_values():
    """A None filter value is a no-op.

    e.g. ``{"reasoning": None}`` should not constrain the catalog.
    """
    from lfx.base.models.unified_models.build_config import _filters_from_build_config

    bc = {"model": {"filters": {"tool_calling": True, "reasoning": None}}}
    assert _filters_from_build_config(bc, "model") == {"tool_calling": True}


def test_augmented_cache_key_prefix_namespaces_by_filters():
    """Different filter configurations must produce different cache keys.

    Sorted-key serialization keeps the prefix stable under argument-order changes.
    """
    from lfx.base.models.unified_models.build_config import _augmented_cache_key_prefix

    assert _augmented_cache_key_prefix("language_model_options", {}) == "language_model_options"
    a = _augmented_cache_key_prefix("language_model_options", {"tool_calling": True})
    b = _augmented_cache_key_prefix("language_model_options", {"reasoning": True})
    c = _augmented_cache_key_prefix("language_model_options", {"tool_calling": True, "reasoning": True})
    assert a != b != c
    # Stable across argument order.
    same = _augmented_cache_key_prefix("language_model_options", {"reasoning": True, "tool_calling": True})
    assert same == c


# ---------------------------------------------------------------------------
# Sticky-default behavior driven by filters
# ---------------------------------------------------------------------------


def test_sticky_default_drops_saved_model_that_fails_filters():
    """A saved tool-incompatible model must not re-appear via sticky-inject.

    Pins the Agent UX: previously-selected ``gemini-3.1-flash-image-preview``
    (or similar) is auto-replaced with a compatible default once the filter
    runs.
    """
    from lfx.base.models.unified_models import build_config as bc

    compatible_options = [
        _llm_option("gemini-3.1-flash-lite"),
        _llm_option("gemma-4-26b-a4b-it"),
    ]
    saved_value = [
        {
            "name": "gemini-3.1-flash-image-preview",
            "provider": "Google Generative AI",
            "metadata": {},
        }
    ]
    build_config = {
        "model": {
            "value": saved_value,
            "options": [],
            "filters": {"tool_calling": True},
        }
    }
    component = _component()

    with patch.object(bc, "_saved_model_passes_filters", return_value=False) as passes:
        result = bc.update_model_options_in_build_config(
            component=component,
            build_config=build_config,
            cache_key_prefix="language_model_options__tool_calling=True",
            get_options_func=lambda user_id=None: compatible_options,  # noqa: ARG005
            field_name=None,
            field_value=None,
        )

    passes.assert_called_once_with("gemini-3.1-flash-image-preview", "Google Generative AI", {"tool_calling": True})
    option_names = {opt["name"] for opt in result["model"]["options"]}
    assert "gemini-3.1-flash-image-preview" not in option_names
    selected = result["model"]["value"]
    assert isinstance(selected, list)
    assert selected, "value should not be empty after auto-default fires"
    assert selected[0]["name"] in {"gemini-3.1-flash-lite", "gemma-4-26b-a4b-it"}


def test_sticky_default_preserves_saved_value_when_filters_satisfied():
    """Saved-but-provider-disabled selections still inject with not_enabled_locally.

    Preserves the original cross-account flow-import UX: a Claude model
    selected on another account stays referenced after import, marked
    ``not_enabled_locally`` so the user can configure the provider.
    """
    from lfx.base.models.unified_models import build_config as bc

    compatible_options = [_llm_option("gemini-2.5-pro")]
    saved_value = [
        {
            "name": "claude-opus-4-7",
            "provider": "Anthropic",
            "metadata": {},
        }
    ]
    build_config = {
        "model": {
            "value": saved_value,
            "options": [],
            "filters": {"tool_calling": True},
        }
    }
    component = _component()

    with patch.object(bc, "_saved_model_passes_filters", return_value=True):
        result = bc.update_model_options_in_build_config(
            component=component,
            build_config=build_config,
            cache_key_prefix="language_model_options__tool_calling=True",
            get_options_func=lambda user_id=None: compatible_options,  # noqa: ARG005
            field_name=None,
            field_value=None,
        )

    option_names = {opt["name"] for opt in result["model"]["options"]}
    assert "claude-opus-4-7" in option_names
    injected = next(opt for opt in result["model"]["options"] if opt["name"] == "claude-opus-4-7")
    assert injected["metadata"].get("not_enabled_locally") is True
    assert result["model"]["value"][0]["name"] == "claude-opus-4-7"


def test_sticky_default_unchanged_when_no_filters_declared():
    """Plain LanguageModel picker (no filters) keeps the original inject path.

    Injects anything missing with ``not_enabled_locally`` and never consults
    the catalog — verified by asserting the helper isn't called.
    """
    from lfx.base.models.unified_models import build_config as bc

    compatible_options = [_llm_option("gemini-2.5-pro")]
    saved_value = [
        {
            "name": "some-old-model",
            "provider": "Anthropic",
            "metadata": {},
        }
    ]
    build_config = {"model": {"value": saved_value, "options": []}}
    component = _component()

    with patch.object(bc, "_saved_model_passes_filters") as passes:
        result = bc.update_model_options_in_build_config(
            component=component,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=lambda user_id=None: compatible_options,  # noqa: ARG005
            field_name=None,
            field_value=None,
        )

    passes.assert_not_called()
    option_names = {opt["name"] for opt in result["model"]["options"]}
    assert "some-old-model" in option_names
    injected = next(opt for opt in result["model"]["options"] if opt["name"] == "some-old-model")
    assert injected["metadata"].get("not_enabled_locally") is True


def test_saved_model_passes_filters_returns_true_for_unknown_models():
    """Unknown models conservatively pass the filter.

    A model name not in the catalog at all (e.g. a user-supplied custom
    model) returns True so we preserve the original inject behavior for
    cases this helper can't actually evaluate.
    """
    from lfx.base.models.unified_models import build_config as bc
    from lfx.base.models.unified_models import model_catalog as mc

    with patch.object(mc, "get_unified_models_detailed", return_value=[]):
        assert bc._saved_model_passes_filters("custom/totally-unknown", "MyProvider", {"tool_calling": True}) is True


def test_saved_model_passes_filters_empty_filters_short_circuits():
    """Empty filters trivially pass.

    Pinned because we don't even consult the catalog when there are no
    constraints to evaluate.
    """
    from lfx.base.models.unified_models import build_config as bc
    from lfx.base.models.unified_models import model_catalog as mc

    with patch.object(mc, "get_unified_models_detailed") as gum:
        result = bc._saved_model_passes_filters("anything", "anyprovider", {})

    assert result is True
    gum.assert_not_called()


def test_saved_model_passes_filters_checks_every_metadata_key():
    """Every key in the filter dict must match.

    A model that passes one constraint but fails another is rejected.
    """
    from lfx.base.models.unified_models import build_config as bc
    from lfx.base.models.unified_models import model_catalog as mc

    fake_catalog = [
        {
            "provider": "Google Generative AI",
            "models": [
                {
                    "model_name": "gemini-2.5-pro",
                    "metadata": {"tool_calling": True, "reasoning": False},
                }
            ],
        }
    ]
    with patch.object(mc, "get_unified_models_detailed", return_value=fake_catalog):
        assert bc._saved_model_passes_filters("gemini-2.5-pro", "Google Generative AI", {"tool_calling": True}) is True
        assert bc._saved_model_passes_filters("gemini-2.5-pro", "Google Generative AI", {"reasoning": True}) is False
        # Both constraints required:
        result = bc._saved_model_passes_filters(
            "gemini-2.5-pro",
            "Google Generative AI",
            {"tool_calling": True, "reasoning": True},
        )
        assert result is False
