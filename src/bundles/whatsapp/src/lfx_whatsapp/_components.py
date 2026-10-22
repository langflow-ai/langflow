"""Configurable WhatsApp actions and a combined message/status receiver."""

from __future__ import annotations

import re
from typing import ClassVar

from lfx.custom import Component
from lfx.integrations.errors import InvalidRequestError
from lfx.integrations.telemetry import integration_action
from lfx.io import ConnectionRefInput
from lfx.schema.data import Data

from lfx_whatsapp._client import SCOPES, WhatsAppClient

AUTH_PROFILE = "whatsapp-system-user"


MAX_TEXT = 4096


def connection_input(capability: str, *, required: bool = True) -> ConnectionRefInput:
    return ConnectionRefInput(
        name="connection",
        display_name="WhatsApp Connection",
        provider="whatsapp",
        auth_profile_id=AUTH_PROFILE,
        identity_kind="instance",
        ownership_mode="user",
        required_scopes=list(SCOPES),
        capabilities=[capability],
        required=required,
        info="Your own system-user token for the server's configured app, WABA and phone.",
    )


def recipient(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{6,14}", value):
        msg = "Use a recipient phone number with country code and digits only."
        raise ValueError(msg)
    return value


def text_body(value: str) -> dict:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        msg = "Message text must contain 1 to 4096 characters."
        raise ValueError(msg)
    return {"body": value, "preview_url": False}


class WhatsAppActionComponent(Component):
    icon = "MessageCircle"
    capability_id: ClassVar[str] = ""

    async def send(self, payload: dict, *, expected_phone: str | None = None, expected_waba: str | None = None) -> Data:
        lease = self.resolve_connection("connection")
        credential = await lease.get_credential()
        async with (
            integration_action(
                self, provider="whatsapp", capability=self.capability_id, owner_kind=credential.owner_kind
            ),
            WhatsAppClient(lease) as client,
        ):
            if expected_phone is not None and (
                expected_phone != client.config.phone_id or expected_waba != client.config.waba_id
            ):
                msg = "Reply using the same WhatsApp business phone that received the event."
                raise InvalidRequestError(msg, provider="whatsapp")
            result = await client.send(payload)
        self.status = "WhatsApp accepted the message. Delivery is reported separately."
        return Data(data=result)
