"""Verify Telegram's secret header before reading a trigger delivery."""

from __future__ import annotations

import hmac
import json
import re

from langflow.services.triggers.ingress.verifiers import (
    IngressRejected,
    IngressRequest,
    IngressSecrets,
    Verified,
)
from langflow.services.triggers.providers.telegram.events import canonical, normalize


def verify(request: IngressRequest, secrets: IngressSecrets, *, tolerance_s: int) -> Verified:
    del tolerance_s
    expected = secrets.signing_secret
    supplied = request.header("X-Telegram-Bot-Api-Secret-Token")
    if (
        not expected
        or not supplied
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", supplied)
        or not hmac.compare_digest(expected.encode(), supplied.encode())
    ):
        msg = "bad_signature"
        raise IngressRejected(msg)
    try:
        body = json.loads(request.body)
    except (ValueError, TypeError):
        msg = "bad_payload"
        raise IngressRejected(msg) from None
    config = secrets.target_config or {}
    if not re.fullmatch(r"[1-9][0-9]{0,15}", str(secrets.resource_id or "")) or not re.fullmatch(
        r"[A-Za-z0-9_]{5,32}", str(secrets.channel_id or "")
    ):
        msg = "bad_receiver"
        raise IngressRejected(msg)
    event = normalize(
        body,
        kind=secrets.target_kind or "",
        config=config,
        bot_id=str(secrets.resource_id or ""),
        bot_username=str(secrets.channel_id or ""),
    )
    if event is None:
        # Telegram retries non-2xx deliveries. Valid but filtered events are
        # acknowledged without inserting an event into the ledger.
        return Verified(source_items=())
    return Verified(source_items=(canonical(event),))
