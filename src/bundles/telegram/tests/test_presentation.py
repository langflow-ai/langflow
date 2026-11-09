"""Presentation names match between the palette and connection permissions."""

import json
from pathlib import Path

import pytest
from lfx.extension import load_extension
from lfx_telegram import TelegramNotifyComponent, TelegramSendMessageComponent
from lfx_telegram.components import telegram as components


@pytest.mark.parametrize("component_name", components.__all__)
def test_palette_and_permissions_use_the_same_provider_labels(component_name):
    component = getattr(components, component_name)
    path = Path(__file__).parents[1] / "src/lfx_telegram/components/telegram/capabilities.v1.json"
    manifest = json.loads(path.read_text())
    capabilities = [item for item in manifest["capabilities"] if item["component_ref"] == component_name]
    assert capabilities
    assert all(item["display_name"] == component.display_name for item in capabilities)
    assert component.display_name.startswith("Telegram: ")
    assert component.icon == manifest["icon"] == "Telegram"


@pytest.mark.parametrize("component", [TelegramNotifyComponent, TelegramSendMessageComponent])
def test_action_target_fields_accept_message_connections(component):
    fields = component().to_frontend_node()["data"]["node"]["template"]
    assert fields["chat_id"]["input_types"] == ["Message"]
    assert fields["thread_id"]["input_types"] == ["Message"]


def test_notification_remains_loadable_as_a_legacy_action_with_a_valid_replacement():
    import lfx_telegram

    loaded = load_extension(Path(lfx_telegram.__file__).parent, distribution="lfx-telegram")
    assert loaded.ok, loaded.errors
    assert TelegramNotifyComponent.legacy is True
    (replacement,) = TelegramNotifyComponent.replacement
    assert replacement == "telegram.TelegramSendMessageComponent"
    category, class_name = replacement.split(".", 1)
    assert any(item.bundle == category and item.class_name == class_name for item in loaded.components)
    assert any(item.class_name == "TelegramNotifyComponent" for item in loaded.components)
    assert getattr(TelegramSendMessageComponent, "legacy", False) is False
