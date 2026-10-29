"""Read one Telegram page and leave confirmation behind the durable cursor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from lfx_telegram._client import TelegramClient

from langflow.services.triggers.providers.telegram.events import canonical, normalize
from langflow.services.triggers.source_errors import SourceConfigurationError
from langflow.services.triggers.source_poll import SourceRound

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease

    from langflow.services.database.models.trigger.model import Trigger


MAX_UPDATES = 100


def _offset(state: dict, now: datetime) -> int | None:
    offset = state.get("offset")
    try:
        fetched = datetime.fromisoformat(state.get("last_fetch_at", ""))
        if fetched.tzinfo is None:
            return None
    except (ValueError, TypeError):
        return None
    # Telegram may choose a lower update ID after a week without updates.
    if type(offset) is int and offset >= 0 and now - fetched < timedelta(days=7):
        return offset
    return None


async def collect(trigger: Trigger, lease: CredentialLease) -> SourceRound:
    previous = dict(trigger.provider_state or {})
    config = dict(trigger.config or {})
    if config.get("mechanism_id") != "telegram.get_updates":
        msg = "Telegram webhooks cannot be collected through getUpdates."
        raise SourceConfigurationError(msg)
    now = datetime.now(timezone.utc)
    async with TelegramClient(lease) as client:
        bot = await client.identity()
        if bot["id"] != previous.get("bot_id"):
            msg = "The Telegram bot changed. Disable and re-enable this trigger."
            raise SourceConfigurationError(msg)
        webhook = await client.call("getWebhookInfo")
        if not isinstance(webhook, dict) or webhook.get("url") != "":
            msg = "This Telegram bot has a webhook. Remove its existing receiver before polling."
            raise SourceConfigurationError(msg)
        payload = {"limit": 100, "timeout": 20, "allowed_updates": ["message"]}
        offset = _offset(previous, now)
        if offset is not None:
            payload["offset"] = offset
        updates = await client.call("getUpdates", **payload)
    if not isinstance(updates, list) or len(updates) > MAX_UPDATES:
        msg = "Telegram returned an invalid update page."
        raise SourceConfigurationError(msg)
    update_ids = [item.get("update_id") for item in updates if isinstance(item, dict)]
    if (
        len(update_ids) != len(updates)
        or any(type(value) is not int or value < 0 for value in update_ids)
        or update_ids != sorted(set(update_ids))
    ):
        msg = "Telegram returned invalid update identities."
        raise SourceConfigurationError(msg)
    events = [
        normalize(update, kind=trigger.kind, config=config, bot_id=bot["id"], bot_username=bot["username"])
        for update in updates
    ]
    # Only the next poll confirms this committed page. Empty polls clear the
    # old offset so a week of inactivity cannot confirm a lower new update ID.
    cursor = {
        "bot_id": bot["id"],
        "bot_username": bot["username"],
        "offset": update_ids[-1] + 1 if update_ids else None,
        "last_fetch_at": now.isoformat(),
    }
    return SourceRound(
        items=[canonical(event) for event in events if event is not None],
        cursor=cursor,
        previous_cursor=previous,
        baseline=False,
        snapshot_resource=None,
        connection_id=trigger.connection_id,
        mechanism_id=config.get("mechanism_id"),
        config=config,
    )
