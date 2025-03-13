"""Component for sending messages to Discord channels."""

import discord
from loguru import logger

from langflow.custom import Component
from langflow.io import DataInput, MultilineInput, Output
from langflow.schema import Data
from langflow.services.deps import get_discord_service


class DiscordSenderComponent(Component):
    display_name = "Discord Message Sender"
    description = "Sends messages to Discord channels in response to received messages."
    icon = "discord"
    name = "DiscordSender"

    inputs = [
        MultilineInput(
            name="message",
            display_name="Message Content",
            info="The message to send to the Discord channel.",
            required=True,
            tool_mode=True,
        ),
        DataInput(
            name="trigger_data",
            display_name="Trigger Data",
            info="Discord trigger data from the received message.",
            required=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Result",
            name="result",
            method="send_discord_message",
            info="The result of the Discord message operation.",
        )
    ]

    async def send_discord_message(self) -> Data:
        """Send a message to the Discord channel where the trigger message was received."""
        # Get the Discord service
        discord_service = get_discord_service()
        if not discord_service or not discord_service.is_started():
            error_msg = "Discord service is not available or not started"
            logger.error(error_msg)
            return Data(data={"success": False, "error": error_msg})

        # Extract channel_id from trigger_data
        channel_id = None
        trigger_data = self.trigger_data.get("trigger_data") if isinstance(self.trigger_data, dict) else None
        if not trigger_data:
            trigger_data = self.ctx.get("discord_trigger_data")
        if not trigger_data:
            error_msg = "Trigger data not found."
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Process trigger data
        if isinstance(trigger_data, list) and len(trigger_data) > 0:
            for item in trigger_data:
                if isinstance(item, dict) and "trigger_data" in item:
                    trigger_info = item["trigger_data"]
                    if "channel_id" in trigger_info:
                        channel_id = trigger_info["channel_id"]
                    break
        else:
            channel_id = trigger_data.get("channel_id")

        # Check if we have a channel_id
        if not channel_id:
            error_msg = "Channel ID not found in trigger data"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Check if we have a message
        if not self.message:
            error_msg = "Message content is required"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Get the channel
            channel = discord_service.bot.get_channel(int(channel_id))
            if not channel:
                try:
                    # Try fetching the channel if it's not in the cache
                    channel = await discord_service.bot.fetch_channel(int(channel_id))
                except discord.NotFound:
                    error_msg = f"Discord channel {channel_id} not found"
                    logger.error(error_msg)
                    return Data(data={"success": False, "error": error_msg})
                except discord.Forbidden:
                    error_msg = f"Not authorized to access Discord channel {channel_id}"
                    logger.error(error_msg)
                    return Data(data={"success": False, "error": error_msg})
                except discord.HTTPException as e:
                    error_msg = f"HTTP error fetching Discord channel {channel_id}: {e}"
                    logger.error(error_msg)
                    return Data(data={"success": False, "error": error_msg})

            # Send the message
            # self.message is a string
            sent_message = await channel.send(self.message)

            return Data(
                data={
                    "success": True,
                    "message_id": str(sent_message.id),
                    "channel_id": str(channel.id),
                    "content": self.message,
                }
            )

        except (ValueError, TypeError) as e:
            # Handle specific exceptions for parameter validation
            error_msg = f"Error with Discord message parameters: {e}"
            logger.error(error_msg)
            return Data(data={"success": False, "error": error_msg})
        except discord.Forbidden:
            # Handle permission issues
            error_msg = "Not authorized to send messages to this Discord channel"
            logger.error(error_msg)
            return Data(data={"success": False, "error": error_msg})
        except discord.HTTPException as e:
            # Handle HTTP errors from Discord API
            error_msg = f"Discord API error: {e}"
            logger.error(error_msg)
            return Data(data={"success": False, "error": error_msg})
        except ConnectionError as e:
            # Handle connection issues
            error_msg = f"Discord connection error: {e}"
            logger.error(error_msg)
            return Data(data={"success": False, "error": error_msg})
        except TimeoutError as e:
            # Handle timeout issues
            error_msg = f"Discord request timed out: {e}"
            logger.error(error_msg)
            return Data(data={"success": False, "error": error_msg})
