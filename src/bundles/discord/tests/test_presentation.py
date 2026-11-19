"""Presentation names match between the palette and connection permissions."""

import json
from pathlib import Path

import pytest
from lfx_discord.components import discord as components


@pytest.mark.parametrize("component_name", components.__all__)
def test_palette_and_permissions_use_the_same_provider_labels(component_name):
    component = getattr(components, component_name)
    path = Path(__file__).parents[1] / "src/lfx_discord/components/discord/capabilities.v1.json"
    manifest = json.loads(path.read_text())
    capabilities = [item for item in manifest["capabilities"] if item["component_ref"] == component_name]
    assert capabilities
    assert all(item["display_name"] == component.display_name for item in capabilities)
    assert component.display_name.startswith("Discord: ")
    assert component.icon == manifest["icon"] == "discord"
