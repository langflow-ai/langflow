"""Installed-bundle entry point for the Telegram server adapter."""

from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider
from langflow.services.triggers.providers.telegram.config import normalize_config
from langflow.services.triggers.providers.telegram.credentials import validate_manual_credential
from langflow.services.triggers.providers.telegram.ingress import verify
from langflow.services.triggers.providers.telegram.lifecycle import ingress_secrets, prepare, provision, revoke
from langflow.services.triggers.providers.telegram.polling import collect

_FIELDS = ("connection", "allowed_chats", "allowed_senders", "session_scope", "delivery_mode")
PROVIDER = TriggerProvider(
    provider_id="telegram",
    bundle="telegram",
    kinds=(
        TriggerKind(
            kind="telegram.message",
            component="TelegramOnMessageTriggerComponent",
            display_name="Telegram: On Message",
            config_fields=_FIELDS,
            identity="bot",
            poll_mechanism="telegram.get_updates",
            push_mechanism="telegram.webhook",
        ),
        TriggerKind(
            kind="telegram.command",
            component="TelegramOnCommandTriggerComponent",
            display_name="Telegram: On Command",
            config_fields=(*_FIELDS, "commands"),
            identity="bot",
            poll_mechanism="telegram.get_updates",
            push_mechanism="telegram.webhook",
        ),
    ),
    normalize_config=normalize_config,
    collect=collect,
    prepare=prepare,
    provision=provision,
    revoke=revoke,
    verify=verify,
    ingress_secrets=ingress_secrets,
    api_origins=("https://api.telegram.org",),
    validate_manual_credential=validate_manual_credential,
)
