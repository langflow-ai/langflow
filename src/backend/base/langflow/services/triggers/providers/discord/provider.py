"""Installed Discord provider descriptor."""

from langflow.services.triggers.providers.discord.config import FIELDS, normalize_config
from langflow.services.triggers.providers.discord.credentials import validate_manual_credential
from langflow.services.triggers.providers.discord.gateway import DiscordGatewayAdapter
from langflow.services.triggers.providers.discord.lifecycle import prepare, revoke
from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider


def listener_factory(trigger):
    return DiscordGatewayAdapter(trigger)


PROVIDER = TriggerProvider(
    provider_id="discord",
    bundle="discord",
    kinds=tuple(
        TriggerKind(
            kind=f"discord.{event}",
            component=f"DiscordOn{event.title()}TriggerComponent",
            display_name=f"Discord: On {event.title()}",
            config_fields=FIELDS,
            identity="bot",
            listener_factory=listener_factory,
            listener_mechanism="discord.gateway",
        )
        for event in ("message", "mention")
    ),
    normalize_config=normalize_config,
    prepare=prepare,
    revoke=revoke,
    api_origins=("https://discord.com",),
    validate_manual_credential=validate_manual_credential,
)
