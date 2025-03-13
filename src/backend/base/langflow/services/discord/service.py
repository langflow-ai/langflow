from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from loguru import logger

from langflow.services.base import Service
from langflow.services.deps import get_trigger_service

if TYPE_CHECKING:
    from langflow.services.database.models.task.model import TaskRead


class DiscordService(Service):
    """Service responsible for interacting with Discord."""

    name = "discord_service"

    def __init__(self):
        """Initialize the Discord service."""
        # Use default intents and only enable what we need
        self.intents = discord.Intents.default()
        self.intents.message_content = True  # This is a privileged intent
        self.bot = commands.Bot(command_prefix="!", intents=self.intents)
        self._is_running = False

        # Setup event handlers
        @self.bot.event
        async def on_ready():
            logger.info(f"Discord bot is ready as {self.bot.user}")

        @self.bot.event
        async def on_message(message):
            # Don't respond to bot's own messages
            if message.author == self.bot.user:
                return

            # Prepare message data
            message_data = {
                "user_id": str(message.author.id),
                "username": message.author.name,
                "content": message.content,
                "channel_id": str(message.channel.id),
                "channel_name": message.channel.name,
                "message_id": str(message.id),
                "timestamp": message.created_at.isoformat(),
                "attachments": [att.url for att in message.attachments],
            }

            # Always process messages directly
            await self._process_message_directly(message_data)

    async def _process_message_directly(self, message_data: dict) -> TaskRead | None:
        """Process a Discord message directly by creating a trigger event.

        This directly creates a task for all flows that are subscribed to Discord message events.

        Args:
            message_data: The Discord message data

        Returns:
            The created task, if any
        """
        try:
            # Get the trigger service
            trigger_service = get_trigger_service()
            if not trigger_service:
                logger.error("Trigger service not available for direct message processing")
                return None

            # Create trigger data
            trigger_data = {
                "source": "discord",
                "discord_user_id": message_data["user_id"],
                "discord_username": message_data["username"],
                "content": message_data["content"],
                "channel_id": message_data["channel_id"],
                "channel_name": message_data["channel_name"],
                "message_id": message_data["message_id"],
                "timestamp": message_data["timestamp"],
                "attachments": message_data["attachments"],
            }

            # Process the event using the trigger service
            task = await trigger_service.process_trigger_event(
                event_type="discord_message_received", trigger_data=trigger_data
            )
            logger.info(f"Created task for Discord message: {task}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error processing Discord message directly: {e}")
            return None
        return task

    async def start(self, token: str) -> None:
        """Start the Discord service.

        Args:
            token: The Discord bot token
        """
        if self._is_running:
            logger.warning("Discord service is already running")
            return

        logger.info("Starting Discord service")
        self._task = asyncio.create_task(self._start_bot(token))
        self._is_running = True

    def is_started(self) -> bool:
        """Check if the Discord service is running."""
        return self._is_running

    async def _start_bot(self, token: str) -> None:
        """Start the Discord bot."""
        try:
            await self.bot.start(token)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error starting Discord bot: {e}")
            self._is_running = False

    async def stop(self) -> None:
        """Stop the Discord service."""
        if not self._is_running:
            logger.warning("Discord service is not running")
            return

        logger.info("Stopping Discord service")
        await self.bot.close()
        self._is_running = False
