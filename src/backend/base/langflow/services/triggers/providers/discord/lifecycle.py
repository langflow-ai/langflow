"""Reserve one receiver per bot without making network calls in admission."""

from lfx_discord._client import DiscordClient, snowflake
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.trigger.model import TriggerCleanup, TriggerSubscription
from langflow.services.triggers.source_errors import SourceConfigurationError
from langflow.services.triggers.subscriptions import audit_subscription_creation

MESSAGE_CONTENT_REQUIRED = "Enable and, when required, obtain approval for Message Content Intent."


async def validate_source(trigger, lease) -> None:
    """Check provider settings before reporting a Gateway receiver as active."""
    async with DiscordClient(lease) as client:
        bot = await client.identity()
        for channel_id in trigger.config["channel_ids"]:
            await client.channel(trigger.config["guild_id"], channel_id)
    if trigger.kind == "discord.message" and not bot["content_enabled"]:
        raise SourceConfigurationError(MESSAGE_CONTENT_REQUIRED, terminal=True)


async def prepare(session, trigger) -> None:
    connection = await session.get(Connection, trigger.connection_id)
    identity = connection.executing_identity if connection else {}
    account = identity.get("account", {})
    if (
        connection is None
        or connection.provider_key != "discord"
        or identity.get("identity") != "bot"
        or not isinstance(account, dict)
    ):
        msg = "Reconnect Discord to verify the bot identity."
        raise SourceConfigurationError(msg)
    bot_id = snowflake(account.get("id"))
    key = f"bot:{bot_id}"

    async def pending():
        return (
            await session.exec(
                select(TriggerCleanup.id).where(
                    TriggerCleanup.provider == "discord", TriggerCleanup.provider_subscription_id == key
                )
            )
        ).first() is not None

    if await pending():
        msg = "Discord receiver cleanup is pending. Retry after it finishes."
        raise SourceConfigurationError(msg)
    row = (
        await session.exec(
            select(TriggerSubscription)
            .where(TriggerSubscription.provider == "discord", TriggerSubscription.provider_subscription_id == key)
            .with_for_update()
        )
    ).first()
    if row is not None and row.state != "expired":
        if row.trigger_id != trigger.id or row.connection_id != trigger.connection_id:
            msg = "This Discord bot already has a receiver. Choose a different bot."
            raise SourceConfigurationError(msg)
        return
    siblings = (
        await session.exec(
            select(TriggerSubscription.id).where(
                TriggerSubscription.trigger_id == trigger.id, TriggerSubscription.state != "expired"
            )
        )
    ).first()
    if siblings is not None:
        msg = "Disable the previous Discord bot receiver before changing its connection."
        raise SourceConfigurationError(msg)
    try:
        async with session.begin_nested():
            if row is not None:
                await session.delete(row)
                await session.flush()
            row = TriggerSubscription(
                trigger_id=trigger.id,
                connection_id=trigger.connection_id,
                provider="discord",
                provider_subscription_id=key,
                state="active",
                provider_state={"bot_id": bot_id, "transport": "discord.gateway"},
            )
            session.add(row)
            await session.flush()
            if await pending():
                msg = "Discord receiver cleanup is pending. Retry after it finishes."
                raise SourceConfigurationError(msg)
    except IntegrityError:
        msg = "This Discord bot already has a receiver. Choose a different bot."
        raise SourceConfigurationError(msg) from None
    await audit_subscription_creation(session, trigger_id=trigger.id)
    trigger.provider_state = {"bot_id": bot_id}
    session.add(trigger)
    await session.flush()


async def revoke(_task, _lease) -> None:
    """The supervisor closes leased sockets. Cleanup never edits an external bot."""
    return
