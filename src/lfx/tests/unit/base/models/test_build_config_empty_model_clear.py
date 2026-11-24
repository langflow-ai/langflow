"""An explicitly cleared model selection must stay empty.

Bug: when ``update_build_config`` receives ``field_name="model"`` with an
empty ``field_value``, the lifecycle filled the value with ``options[0]``.
``options`` is one flat list across every enabled provider, so the injected
model belongs to whichever provider happens to iterate first — a provider
the node was never configured for. Because ``POST /api/v2/workflows``
carries the live-canvas ``data`` override, the substituted model is what
actually executes, silently, billed to the wrong provider account.

LE-2168 narrowed it again: a bare initial load (``field_name=None``, a freshly
dropped node or a reopened flow) no longer falls back to ``options[0]`` either,
because an unvalidated credential harvested from the environment is enough to
mark a provider enabled, so the fallback pre-selected a provider the user never
set up. Only the user's stored ``__default_language_model__`` fills there. A
user-triggered update such as entering an api_key still fills, and so does the
replacement of a selection that filters or provider policy just took away.
See ``test_build_config_no_unconfigured_default.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

from lfx.base.models.unified_models.build_config import (
    handle_model_input_update,
    update_model_options_in_build_config,
)


def _component(user_id: str = "u-1") -> SimpleNamespace:
    return SimpleNamespace(user_id=user_id, cache={}, inputs=[])


def _multi_provider_options() -> list[dict]:
    """Options spanning several providers, mirroring get_language_model_options."""
    return [
        {"name": "claude-sonnet-4-5", "provider": "Anthropic", "icon": "Anthropic", "metadata": {}},
        {"name": "gemini-2.5-flash", "provider": "Google Generative AI", "icon": "GoogleGenerativeAI", "metadata": {}},
        {"name": "gpt-4o-mini", "provider": "OpenAI", "icon": "OpenAI", "metadata": {}},
    ]


def _get_options(user_id=None):  # noqa: ARG001
    return _multi_provider_options()


class TestExplicitModelClearStaysEmpty:
    def test_empty_model_update_is_not_filled_from_another_provider(self):
        """The deterministic repro: field_name="model", field_value=[] must stay empty."""
        build_config = {"model": {"value": [], "options": []}}

        result = handle_model_input_update(
            component=_component(),
            build_config=build_config,
            field_value=[],
            field_name="model",
            get_options_func=_get_options,
        )

        assert not result["model"]["value"], (
            f"an explicitly cleared model selection must stay empty, got {result['model']['value']!r}"
        )

    def test_empty_model_update_clears_stale_build_config_value(self):
        """An explicit clear wins over a stale non-empty value in build_config."""
        build_config = {
            "model": {
                "value": [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}],
                "options": [],
            }
        }

        result = handle_model_input_update(
            component=_component(),
            build_config=build_config,
            field_value=[],
            field_name="model",
            get_options_func=_get_options,
        )

        assert not result["model"]["value"]

    def test_empty_model_update_with_no_options_stays_empty(self):
        """Clear with zero configured providers keeps today's empty result."""
        build_config = {"model": {"value": [], "options": []}}

        result = handle_model_input_update(
            component=_component(),
            build_config=build_config,
            field_value=[],
            field_name="model",
            get_options_func=lambda user_id=None: [],  # noqa: ARG005
        )

        assert not result["model"]["value"]

    def test_valid_selection_is_preserved(self):
        """A valid explicit selection still round-trips untouched."""
        selection = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]
        build_config = {"model": {"value": selection, "options": []}}

        result = handle_model_input_update(
            component=_component(),
            build_config=build_config,
            field_value=selection,
            field_name="model",
            get_options_func=_get_options,
        )

        assert result["model"]["value"][0]["name"] == "gpt-4o-mini"
        assert result["model"]["value"][0]["provider"] == "OpenAI"


class TestAutoDefaultNoLongerGuessesAProvider:
    def test_initial_load_does_not_auto_fill_without_explicit_default(self):
        """field_name=None (new node dropped on canvas) must not guess a provider (LE-2168)."""
        build_config = {"model": {"value": [], "options": []}}

        result = update_model_options_in_build_config(
            component=_component(),
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=_get_options,
            field_name=None,
            field_value=None,
        )

        assert not result["model"]["value"]

    def test_non_model_field_trigger_still_auto_fills(self):
        """A non-model trigger (e.g. api_key entry) is an explicit act and keeps the fill."""
        build_config = {"model": {"value": [], "options": []}}

        result = update_model_options_in_build_config(
            component=_component(),
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=_get_options,
            field_name="api_key",
            field_value="sk-test",
        )

        assert result["model"]["value"]

    def test_model_refresh_with_existing_selection_is_preserved(self):
        """Refresh (field_name="model") with a real selection never rewrites it."""
        selection = [{"name": "gemini-2.5-flash", "provider": "Google Generative AI", "metadata": {}}]
        build_config = {"model": {"value": selection, "options": []}}

        result = update_model_options_in_build_config(
            component=_component(),
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=_get_options,
            field_name="model",
            field_value=selection,
        )

        assert result["model"]["value"][0]["name"] == "gemini-2.5-flash"

    def test_model_clear_does_not_auto_fill_in_options_refresh(self):
        """The options-refresh helper itself must honor an explicit clear."""
        build_config = {"model": {"value": [], "options": []}}

        result = update_model_options_in_build_config(
            component=_component(),
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=_get_options,
            field_name="model",
            field_value=[],
        )

        assert not result["model"]["value"]
