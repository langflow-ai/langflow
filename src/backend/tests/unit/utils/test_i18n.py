"""Unit tests for the backend i18n utility (``langflow.utils.i18n``).

Covers the translation lookup, locale discovery, locale-file loading, and the
component/starter-flow translation helpers. ``translate_flow_notes`` and
``_safe_flow_key`` are covered separately in ``test_i18n_note_translation``.
"""

import copy
import json
from types import SimpleNamespace

from langflow.utils import i18n
from langflow.utils.i18n import (
    build_component_display_names,
    get_supported_locales,
    translate,
    translate_component_dict,
    translate_component_node,
    translate_starter_flows,
)
from langflow.utils.i18n_keys import component_field_key, normalize_component_key

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_translations(monkeypatch, translations):
    """Install a fixed translations table so no real locale files are loaded."""
    monkeypatch.setattr("langflow.utils.i18n._translations", translations)


# ---------------------------------------------------------------------------
# translate()
# ---------------------------------------------------------------------------


class TestTranslate:
    def test_returns_value_from_requested_locale(self, monkeypatch):
        _set_translations(monkeypatch, {"en": {"k": "Hello"}, "fr": {"k": "Bonjour"}})
        assert translate("k", "fr", "default") == "Bonjour"

    def test_falls_back_to_english_when_locale_missing_key(self, monkeypatch):
        _set_translations(monkeypatch, {"en": {"k": "Hello"}, "fr": {}})
        assert translate("k", "fr", "default") == "Hello"

    def test_falls_back_to_english_when_locale_absent(self, monkeypatch):
        _set_translations(monkeypatch, {"en": {"k": "Hello"}})
        assert translate("k", "ja", "default") == "Hello"

    def test_falls_back_to_default_when_key_unknown(self, monkeypatch):
        _set_translations(monkeypatch, {"en": {}, "fr": {}})
        assert translate("missing", "fr", "the default") == "the default"

    def test_requested_locale_takes_priority_over_english(self, monkeypatch):
        _set_translations(monkeypatch, {"en": {"k": "Hello"}, "fr": {"k": "Bonjour"}})
        assert translate("k", "fr", "default") == "Bonjour"

    def test_empty_string_translation_is_returned(self, monkeypatch):
        # An explicit empty translated value is a real result, not a miss.
        _set_translations(monkeypatch, {"fr": {"k": ""}, "en": {"k": "Hello"}})
        assert translate("k", "fr", "default") == ""

    def test_triggers_load_when_table_empty(self, monkeypatch):
        _set_translations(monkeypatch, {})
        called = {"n": 0}

        def fake_load():
            called["n"] += 1
            i18n._translations["en"] = {"k": "Loaded"}

        monkeypatch.setattr("langflow.utils.i18n._load_translations", fake_load)
        assert translate("k", "en", "default") == "Loaded"
        assert called["n"] == 1


# ---------------------------------------------------------------------------
# get_supported_locales()
# ---------------------------------------------------------------------------


class TestGetSupportedLocales:
    def test_returns_loaded_locale_codes(self, monkeypatch):
        _set_translations(monkeypatch, {"en": {}, "fr": {}, "zh-Hans": {}})
        assert sorted(get_supported_locales()) == ["en", "fr", "zh-Hans"]

    def test_empty_when_no_translations(self, monkeypatch):
        _set_translations(monkeypatch, {})
        monkeypatch.setattr("langflow.utils.i18n._load_translations", lambda: None)
        assert get_supported_locales() == []


# ---------------------------------------------------------------------------
# _load_translations()
# ---------------------------------------------------------------------------


class TestLoadTranslations:
    def test_loads_json_files_from_locales_dir(self, monkeypatch, tmp_path):
        (tmp_path / "en.json").write_text(json.dumps({"k": "Hello"}), encoding="utf-8")
        (tmp_path / "fr.json").write_text(json.dumps({"k": "Bonjour"}), encoding="utf-8")
        _set_translations(monkeypatch, {})
        monkeypatch.setattr("langflow.utils.i18n._LOCALES_DIR", tmp_path)

        i18n._load_translations()

        assert i18n._translations["en"] == {"k": "Hello"}
        assert i18n._translations["fr"] == {"k": "Bonjour"}

    def test_locale_code_comes_from_file_stem(self, monkeypatch, tmp_path):
        (tmp_path / "zh-Hans.json").write_text(json.dumps({"k": "你好"}), encoding="utf-8")
        _set_translations(monkeypatch, {})
        monkeypatch.setattr("langflow.utils.i18n._LOCALES_DIR", tmp_path)

        i18n._load_translations()

        assert "zh-Hans" in i18n._translations

    def test_is_noop_when_already_loaded(self, monkeypatch, tmp_path):
        (tmp_path / "en.json").write_text(json.dumps({"k": "FromDisk"}), encoding="utf-8")
        _set_translations(monkeypatch, {"en": {"k": "Preloaded"}})
        monkeypatch.setattr("langflow.utils.i18n._LOCALES_DIR", tmp_path)

        i18n._load_translations()

        # Existing table is kept; disk file is not read again.
        assert i18n._translations["en"] == {"k": "Preloaded"}

    def test_missing_locales_dir_is_safe(self, monkeypatch, tmp_path):
        _set_translations(monkeypatch, {})
        monkeypatch.setattr("langflow.utils.i18n._LOCALES_DIR", tmp_path / "does_not_exist")

        i18n._load_translations()

        assert i18n._translations == {}

    def test_invalid_json_is_skipped_without_raising(self, monkeypatch, tmp_path):
        (tmp_path / "en.json").write_text(json.dumps({"k": "Hello"}), encoding="utf-8")
        (tmp_path / "broken.json").write_text("{ not valid json", encoding="utf-8")
        _set_translations(monkeypatch, {})
        monkeypatch.setattr("langflow.utils.i18n._LOCALES_DIR", tmp_path)

        i18n._load_translations()

        assert i18n._translations["en"] == {"k": "Hello"}
        assert "broken" not in i18n._translations


# ---------------------------------------------------------------------------
# translate_starter_flows()
# ---------------------------------------------------------------------------


def _flow(name, description=""):
    return SimpleNamespace(name=name, description=description)


class TestTranslateStarterFlows:
    def test_translates_name_and_description(self, monkeypatch):
        _set_translations(
            monkeypatch,
            {
                "fr": {
                    "starter_flows.simple_agent.name": "Agent Simple",
                    "starter_flows.simple_agent.description": "Un agent",
                }
            },
        )
        [out] = translate_starter_flows([_flow("Simple Agent", "An agent")], "fr")
        assert out.name == "Agent Simple"
        assert out.description == "Un agent"

    def test_sets_name_key(self, monkeypatch):
        _set_translations(monkeypatch, {"fr": {}})
        [out] = translate_starter_flows([_flow("Simple Agent")], "fr")
        assert out.name_key == "simple_agent"

    def test_falls_back_to_original_name(self, monkeypatch):
        _set_translations(monkeypatch, {"fr": {}})
        [out] = translate_starter_flows([_flow("Simple Agent", "An agent")], "fr")
        assert out.name == "Simple Agent"
        assert out.description == "An agent"

    def test_does_not_mutate_input(self, monkeypatch):
        _set_translations(monkeypatch, {"fr": {"starter_flows.simple_agent.name": "Agent Simple"}})
        original = _flow("Simple Agent", "An agent")
        translate_starter_flows([original], "fr")
        assert original.name == "Simple Agent"
        assert not hasattr(original, "name_key")

    def test_handles_none_name_and_description(self, monkeypatch):
        _set_translations(monkeypatch, {"fr": {}})
        [out] = translate_starter_flows([_flow(None, None)], "fr")
        assert out.name == ""
        assert out.name_key == ""

    def test_empty_input_returns_empty_list(self, monkeypatch):
        _set_translations(monkeypatch, {"fr": {}})
        assert translate_starter_flows([], "fr") == []


# ---------------------------------------------------------------------------
# translate_component_node()
# ---------------------------------------------------------------------------


class TestTranslateComponentNode:
    def test_translates_component_level_fields(self, monkeypatch):
        norm = normalize_component_key("Chat Input")
        _set_translations(
            monkeypatch,
            {
                "fr": {
                    component_field_key(norm, "display_name", "Chat Input"): "Entree de chat",
                    component_field_key(norm, "description", "Get chat inputs"): "Recuperer",
                }
            },
        )
        node = {"display_name": "Chat Input", "description": "Get chat inputs"}
        out = translate_component_node("Chat Input", node, "fr")
        assert out["display_name"] == "Entree de chat"
        assert out["description"] == "Recuperer"

    def test_translates_template_field_subkeys(self, monkeypatch):
        norm = normalize_component_key("Chat Input")
        _set_translations(
            monkeypatch,
            {
                "fr": {
                    component_field_key(norm, "inputs.text.display_name", "Text"): "Texte",
                    component_field_key(norm, "inputs.text.info", "The text"): "Le texte",
                    component_field_key(norm, "inputs.text.placeholder", "Type here"): "Tapez ici",
                }
            },
        )
        node = {"template": {"text": {"display_name": "Text", "info": "The text", "placeholder": "Type here"}}}
        out = translate_component_node("Chat Input", node, "fr")
        field = out["template"]["text"]
        assert field["display_name"] == "Texte"
        assert field["info"] == "Le texte"
        assert field["placeholder"] == "Tapez ici"

    def test_translates_output_fields(self, monkeypatch):
        norm = normalize_component_key("Chat Input")
        _set_translations(
            monkeypatch,
            {
                "fr": {
                    component_field_key(norm, "outputs.message.display_name", "Message"): "Msg",
                }
            },
        )
        node = {"outputs": [{"name": "message", "display_name": "Message"}]}
        out = translate_component_node("Chat Input", node, "fr")
        assert out["outputs"][0]["display_name"] == "Msg"

    def test_tool_mode_output_uses_shared_sentinel_norm(self, monkeypatch):
        from lfx.base.tools.constants import TOOL_OUTPUT_NAME

        _set_translations(
            monkeypatch,
            {
                "fr": {
                    component_field_key(
                        "_toolmode", f"outputs.{TOOL_OUTPUT_NAME}.display_name", "Toolset"
                    ): "Boite a outils",
                }
            },
        )
        node = {"outputs": [{"name": TOOL_OUTPUT_NAME, "display_name": "Toolset"}]}
        out = translate_component_node("Any Component", node, "fr")
        assert out["outputs"][0]["display_name"] == "Boite a outils"

    def test_does_not_mutate_input_node(self, monkeypatch):
        norm = normalize_component_key("Chat Input")
        _set_translations(
            monkeypatch,
            {"fr": {component_field_key(norm, "display_name", "Chat Input"): "Entree"}},
        )
        node = {
            "display_name": "Chat Input",
            "template": {"text": {"display_name": "Text"}},
            "outputs": [{"name": "message", "display_name": "Message"}],
        }
        snapshot = copy.deepcopy(node)
        translate_component_node("Chat Input", node, "fr")
        assert node == snapshot

    def test_untranslated_values_fall_back_to_english(self, monkeypatch):
        _set_translations(monkeypatch, {"fr": {}})
        node = {"display_name": "Chat Input"}
        out = translate_component_node("Chat Input", node, "fr")
        assert out["display_name"] == "Chat Input"

    def test_idempotent_translation(self, monkeypatch):
        norm = normalize_component_key("Chat Input")
        _set_translations(
            monkeypatch,
            {"fr": {component_field_key(norm, "display_name", "Chat Input"): "Entree"}},
        )
        node = {"display_name": "Chat Input"}
        once = translate_component_node("Chat Input", node, "fr")
        twice = translate_component_node("Chat Input", once, "fr")
        assert twice["display_name"] == "Entree"

    def test_non_dict_template_field_is_ignored(self, monkeypatch):
        _set_translations(monkeypatch, {"fr": {}})
        node = {"template": {"_type": "SomeType", "text": {"display_name": "Text"}}}
        out = translate_component_node("Chat Input", node, "fr")
        assert out["template"]["_type"] == "SomeType"

    def test_empty_fields_are_left_untouched(self, monkeypatch):
        _set_translations(monkeypatch, {"fr": {}})
        node = {"display_name": "", "description": ""}
        out = translate_component_node("Chat Input", node, "fr")
        assert out["display_name"] == ""


# ---------------------------------------------------------------------------
# translate_component_dict()
# ---------------------------------------------------------------------------


class TestTranslateComponentDict:
    def test_translates_all_components_across_categories(self, monkeypatch):
        norm = normalize_component_key("Chat Input")
        _set_translations(
            monkeypatch,
            {"fr": {component_field_key(norm, "display_name", "Chat Input"): "Entree"}},
        )
        all_types = {"inputs": {"Chat Input": {"display_name": "Chat Input"}}}
        out = translate_component_dict(all_types, "fr")
        assert out["inputs"]["Chat Input"]["display_name"] == "Entree"

    def test_does_not_mutate_original(self, monkeypatch):
        norm = normalize_component_key("Chat Input")
        _set_translations(
            monkeypatch,
            {"fr": {component_field_key(norm, "display_name", "Chat Input"): "Entree"}},
        )
        all_types = {"inputs": {"Chat Input": {"display_name": "Chat Input"}}}
        snapshot = copy.deepcopy(all_types)
        translate_component_dict(all_types, "fr")
        assert all_types == snapshot

    def test_preserves_category_structure(self, monkeypatch):
        _set_translations(monkeypatch, {"fr": {}})
        all_types = {
            "inputs": {"Chat Input": {"display_name": "Chat Input"}},
            "outputs": {"Chat Output": {"display_name": "Chat Output"}},
        }
        out = translate_component_dict(all_types, "fr")
        assert set(out) == {"inputs", "outputs"}
        assert set(out["inputs"]) == {"Chat Input"}

    def test_empty_dict_returns_empty(self, monkeypatch):
        _set_translations(monkeypatch, {"fr": {}})
        assert translate_component_dict({}, "fr") == {}


# ---------------------------------------------------------------------------
# build_component_display_names()
# ---------------------------------------------------------------------------


class TestBuildComponentDisplayNames:
    def test_includes_english_baseline(self, monkeypatch):
        _set_translations(monkeypatch, {"en": {}})
        all_types = {"inputs": {"Chat Input": {"display_name": "Chat Input", "description": "desc"}}}
        result = build_component_display_names(all_types)
        norm = normalize_component_key("Chat Input")
        assert "Chat Input" in result[norm]["display_name"]
        assert "desc" in result[norm]["description"]

    def test_includes_all_locale_values(self, monkeypatch):
        norm = normalize_component_key("Chat Input")
        _set_translations(
            monkeypatch,
            {
                "en": {},
                "fr": {component_field_key(norm, "display_name", "Chat Input"): "Entree"},
                "de": {component_field_key(norm, "display_name", "Chat Input"): "Eingabe"},
            },
        )
        all_types = {"inputs": {"Chat Input": {"display_name": "Chat Input"}}}
        names = build_component_display_names(all_types)[norm]["display_name"]
        assert set(names) == {"Chat Input", "Entree", "Eingabe"}

    def test_collects_field_display_names(self, monkeypatch):
        norm = normalize_component_key("Chat Input")
        _set_translations(
            monkeypatch,
            {"fr": {component_field_key(norm, "inputs.text.display_name", "Text"): "Texte"}},
        )
        all_types = {"inputs": {"Chat Input": {"template": {"text": {"display_name": "Text"}}}}}
        fields = build_component_display_names(all_types)[norm]["fields"]
        assert set(fields["text"]["display_name"]) == {"Text", "Texte"}

    def test_component_without_strings_yields_empty_lists(self, monkeypatch):
        _set_translations(monkeypatch, {"en": {}})
        all_types = {"inputs": {"Bare": {}}}
        result = build_component_display_names(all_types)
        norm = normalize_component_key("Bare")
        assert result[norm] == {"display_name": [], "description": [], "fields": {}}

    def test_non_dict_template_field_skipped(self, monkeypatch):
        _set_translations(monkeypatch, {"en": {}})
        all_types = {"inputs": {"Chat Input": {"template": {"_type": "X", "text": {"display_name": "Text"}}}}}
        norm = normalize_component_key("Chat Input")
        fields = build_component_display_names(all_types)[norm]["fields"]
        assert "_type" not in fields
        assert "text" in fields
