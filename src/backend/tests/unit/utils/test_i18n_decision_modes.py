"""Decision Type changes keep the component's labels and help translated."""

import json
from pathlib import Path

import langflow
import pytest
from langflow.utils.i18n import translate_component_node
from langflow.utils.i18n_keys import component_field_key
from lfx.components.llm_operations.decision_model import DecisionModelComponent
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent

LOCALES = ("de", "es", "fr", "ja", "ko", "pt", "zh-Hans")
LOCALES_DIR = Path(langflow.__file__).parent / "locales"


def _assert_translated(component: str, template: dict, fields: tuple[tuple[str, str], ...], locale: str) -> None:
    catalogs = {code: json.loads((LOCALES_DIR / f"{code}.json").read_text(encoding="utf-8")) for code in ("en", locale)}
    node = {"name": component, "template": template}
    translated = translate_component_node(component, node, locale)["template"]
    for field, attribute in fields:
        english = template[field][attribute]
        key = component_field_key(component.lower(), f"inputs.{field}.{attribute}", english)
        assert catalogs["en"][key] == english
        assert translated[field][attribute] == catalogs[locale][key]
        assert translated[field][attribute] != english


@pytest.mark.parametrize("locale", LOCALES)
def test_decision_model_score_fields_are_translated(locale):
    template = {"candidates": {}}
    DecisionModelComponent._show_fields(template, "Score")

    _assert_translated("DecisionModel", template, (("candidates", "display_name"), ("candidates", "info")), locale)


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("kind", ["Boolean", "Score"])
def test_smart_router_decision_type_help_is_translated(locale, kind):
    template = {
        "decision_kind": {"value": kind},
        "decision_question": {},
        "minimum_probability": {},
        "enable_else_output": {},
        "custom_prompt": {"value": "Keep this instruction for language mode."},
    }
    SmartRouterComponent()._show_fields(template, "Decision Model", "routing_mode")

    _assert_translated(
        "SmartRouter",
        template,
        (
            ("decision_question", "info"),
            ("minimum_probability", "info"),
            ("enable_else_output", "info"),
            ("custom_prompt", "info"),
        ),
        locale,
    )
