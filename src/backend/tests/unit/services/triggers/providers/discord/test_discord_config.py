"""Discord configuration errors survive the source validation boundary."""

import pytest
from langflow.services.triggers import source_arming
from langflow.services.triggers.providers import registry
from langflow.services.triggers.providers.discord.provider import PROVIDER


@pytest.mark.parametrize("kind", ["discord.message", "discord.mention"])
@pytest.mark.parametrize("field", ["channel_ids", "guild_id"])
def test_invalid_discord_ids_keep_the_actionable_error(monkeypatch, kind, field):
    extension = next(item for item in PROVIDER.kinds if item.kind == kind)
    monkeypatch.setattr(source_arming, "source_kinds", lambda: (kind,))
    monkeypatch.setattr(source_arming, "get_kind", lambda _kind: extension)
    monkeypatch.setattr(registry, "get_provider", lambda _provider: PROVIDER)
    config = {"connection": "discord/work", "guild_id": "222", "channel_ids": ["333"]}
    config[field] = ["abc"] if field == "channel_ids" else "abc"

    with pytest.raises(ValueError, match=r"Use a numeric Discord ID copied from developer mode\."):
        source_arming.normalize_source_config(kind, config)
