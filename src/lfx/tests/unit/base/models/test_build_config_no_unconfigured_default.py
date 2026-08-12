"""A model must not be auto-selected from a provider the user never configured.

Bug (LE-2168): on a fresh install, dropping a Language Model / Agent node filled the
model field with ``options[0]`` — the first default model of the first enabled provider
in alphabetical order. Providers are marked enabled purely because a credential exists
(``skip_validation=True``), and Langflow harvests ``GOOGLE_API_KEY`` / ``OPENAI_API_KEY``
/ ``ANTHROPIC_API_KEY`` from the environment into global variables. So a key the user
never entered anywhere silently produced a pre-selected model — Gemini when only Google
was present, Claude when Anthropic sorted first.

The user's explicit ``__default_language_model__`` preference remains the one source of
an auto-selection; without it the field stays empty so the user picks. The preference
lives in the database variable service, which only exists in the full langflow install —
those cases are covered in ``src/backend/tests/unit/test_model_input_default_selection.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

from lfx.base.models.unified_models.build_config import update_model_options_in_build_config


def _component(user_id: str = "3f1a0c9e-5b7d-4f2a-9c3e-1d2b3a4c5d6e") -> SimpleNamespace:
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


def _update(build_config: dict, field_name: str | None, field_value):
    return update_model_options_in_build_config(
        component=_component(),
        build_config=build_config,
        cache_key_prefix="language_model_options",
        get_options_func=_get_options,
        field_name=field_name,
        field_value=field_value,
    )


class TestNoAutoSelectionWithoutExplicitDefault:
    def test_initial_load_leaves_model_empty_without_user_default(self):
        """The deterministic repro: a freshly dropped node must not pick a model itself."""
        result = _update({"model": {"value": [], "options": []}}, field_name=None, field_value=None)

        assert not result["model"]["value"], f"no provider was explicitly configured, got {result['model']['value']!r}"

    def test_api_key_entry_still_selects_a_model(self):
        """Typing a key is an explicit configuration act, so the convenience fill stays.

        Note this still picks ``options[0]`` across all enabled providers rather than the
        provider whose key was just entered — a narrower defect left untouched here.
        """
        result = _update({"model": {"value": [], "options": []}}, field_name="api_key", field_value="sk-test")

        assert result["model"]["value"]

    def test_options_are_still_populated_when_nothing_is_selected(self):
        """Bounding the auto-selection must not hide the dropdown contents."""
        result = _update({"model": {"value": [], "options": []}}, field_name=None, field_value=None)

        assert [opt["name"] for opt in result["model"]["options"]] == [
            "claude-sonnet-4-5",
            "gemini-2.5-flash",
            "gpt-4o-mini",
        ]

    def test_existing_selection_is_never_overwritten(self):
        """A model already on the node survives the refresh untouched."""
        selection = [{"name": "gemini-2.5-flash", "provider": "Google Generative AI", "metadata": {}}]

        result = _update({"model": {"value": selection, "options": []}}, field_name=None, field_value=None)

        assert result["model"]["value"][0]["name"] == "gemini-2.5-flash"
