"""Component strings are translated whichever registry key a component is filed under."""

from __future__ import annotations

import json
from pathlib import Path

import langflow
from langflow.utils.i18n import build_component_display_names, translate_component_node
from langflow.utils.i18n_keys import component_field_key

_LOCALES = Path(langflow.__file__).parent / "locales"
_SLACK_DESCRIPTION = (
    "Run this flow when someone posts in Slack: in a channel, a private channel, a direct message or a group DM, "
    "or when they mention the app."
)


def _locale(code: str) -> dict[str, str]:
    return json.loads((_LOCALES / f"{code}.json").read_text(encoding="utf-8"))


def _slack_node() -> dict:
    return {
        "name": "SlackOnMessageTrigger",
        "display_name": "Slack: On Message",
        "description": _SLACK_DESCRIPTION,
        "template": {"connection": {"display_name": "Slack Connection"}},
        "outputs": [{"name": "message", "display_name": "Message"}],
    }


def test_a_bundle_component_is_translated_by_its_name_not_its_namespaced_registry_key() -> None:
    """Bundles register as ``ext:<bundle>:<Class>@<slot>``; their locale keys use the component name."""
    pt = _locale("pt")

    translated = translate_component_node("ext:slack:SlackOnMessageTriggerComponent@official", _slack_node(), "pt")

    assert (
        translated["description"] == pt[component_field_key("slackonmessagetrigger", "description", _SLACK_DESCRIPTION)]
    )
    assert translated["description"] != _SLACK_DESCRIPTION
    assert (
        translated["template"]["connection"]["display_name"]
        == pt[component_field_key("slackonmessagetrigger", "inputs.connection.display_name", "Slack Connection")]
    )


def test_a_component_without_a_name_falls_back_to_its_registry_key() -> None:
    description = "Run this flow on a cron schedule, evaluated in a timezone you choose."
    node = {"display_name": "Schedule", "description": description}

    translated = translate_component_node("ScheduleTrigger", node, "ja")

    assert (
        translated["description"] == _locale("ja")[component_field_key("scheduletrigger", "description", description)]
    )


def test_the_known_display_names_of_a_bundle_component_include_its_translations() -> None:
    all_types = {"slack": {"ext:slack:SlackOnMessageTriggerComponent@official": _slack_node()}}

    known = build_component_display_names(all_types)["ext:slack:slackonmessagetriggercomponent@official"]

    assert (
        _locale("pt")[component_field_key("slackonmessagetrigger", "description", _SLACK_DESCRIPTION)]
        in known["description"]
    )


def _schedule_node() -> dict:
    return {
        "name": "ScheduleTrigger",
        "display_name": "Schedule",
        "template": {
            "schedule_type": {"options": ["Daily", "Weekly"], "translate_options": True, "value": "Weekly"},
            "timezone": {"options": ["UTC", "Europe/Lisbon"], "value": "UTC"},
        },
    }


def test_options_marked_for_translation_get_labels_and_keep_their_values() -> None:
    zh = _locale("zh-Hans")

    translated = translate_component_node("ScheduleTrigger", _schedule_node(), "zh-Hans")

    field = translated["template"]["schedule_type"]
    assert field["options"] == ["Daily", "Weekly"]
    assert field["value"] == "Weekly"
    assert field["option_labels"] == {
        option: zh[component_field_key("scheduletrigger", "inputs.schedule_type.options", option)]
        for option in ("Daily", "Weekly")
    }
    assert field["option_labels"]["Weekly"] != "Weekly"
    assert "option_labels" not in translated["template"]["timezone"]


def test_every_schedule_option_is_translated_in_every_locale() -> None:
    """The picker is unusable in a language that shows half its choices in English."""
    from lfx.base.triggers.schedule import SCHEDULE_TYPES, WEEKDAYS

    expected = {("schedule_type", option) for option in SCHEDULE_TYPES} | {("days_of_week", day) for day in WEEKDAYS}
    for code in ("de", "es", "fr", "ja", "ko", "pt", "zh-Hans"):
        locale = _locale(code)
        missing = [
            option
            for field, option in expected
            if component_field_key("scheduletrigger", f"inputs.{field}.options", option) not in locale
        ]
        assert missing == [], f"{code} is missing {missing}"
