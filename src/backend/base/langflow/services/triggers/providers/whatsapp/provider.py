"""Installed WhatsApp extension descriptor."""

from lfx_whatsapp._client import ORIGIN, SCOPES

from langflow.services.triggers.providers.registry import TriggerKind, TriggerProvider
from langflow.services.triggers.providers.whatsapp.config import normalize_config
from langflow.services.triggers.providers.whatsapp.credentials import validate_manual_credential
from langflow.services.triggers.providers.whatsapp.events import verify, verify_get
from langflow.services.triggers.providers.whatsapp.lifecycle import ingress_secrets, prepare, provision, revoke

PROVIDER = TriggerProvider(
    provider_id="whatsapp",
    bundle="whatsapp",
    kinds=(
        TriggerKind(
            kind="whatsapp.event",
            component="WhatsAppOnEventTriggerComponent",
            display_name="WhatsApp On Message or Status",
            config_fields=("connection", "allowed_senders", "receive_messages", "receive_statuses", "delivery_mode"),
            required_scopes=SCOPES,
            identity="service",
            push_mechanism="whatsapp.webhook",
        ),
    ),
    normalize_config=normalize_config,
    prepare=prepare,
    provision=provision,
    revoke=revoke,
    ingress_secrets=ingress_secrets,
    verify=verify,
    verify_get=verify_get,
    api_origins=(ORIGIN,),
    validate_manual_credential=validate_manual_credential,
)
