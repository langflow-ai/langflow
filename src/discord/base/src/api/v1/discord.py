from typing import Optional, Dict, Any, List
from pydantic import BaseModel, model_validator
from fastapi import APIRouter, Response
from asyncio import get_running_loop, Future, wait_for
from discord.ext import commands
from discord import Intents, File, Sticker, Message
from json import dumps
import base64
import io
import random
import soundfile as sf


router = APIRouter(tags=["Discord"])


class TokenModel(BaseModel):
    token: str


class ChannelMessagesModel(TokenModel):
    limit: int = 20
    timeout: int = 5 * 60
    ignore_file_content: bool = True
    ignore_attachments: bool = True


class ChannelLastFileMessageModel(TokenModel):
    limit: int = 20
    timeout: int = 5 * 60


class ChannelByContentTypeMessageModel(TokenModel):
    content_type: List[str]
    limit: int = 20
    timeout: int = 5 * 60


class GetGuildUsersModel(TokenModel):
    guild_id: Optional[int] = None
    channel_id: Optional[int] = None

    @model_validator(mode="after")
    def verify(self):
        if not self.guild_id and not self.channel_id:
            raise ValueError("The fields guild_id and channel_id cannot be both None")
        return self


class GetGuildChannelsModel(TokenModel):
    type: Optional[str] = None


class Listener(TokenModel):
    channel_id: int
    timeout: int = 5 * 60


class MentionListener(TokenModel):
    guild_id: Optional[int] = None
    channel_id: Optional[int] = None
    timeout: int = 5 * 60


class SendMessageModel(TokenModel):
    message: Optional[str] = None
    sticker_id: Optional[str] = None
    filename: Optional[str] = None
    type: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    is_audio: bool = False
    reference: Optional[int] = None


class ReactionModel(TokenModel):
    emoji: str


@router.post("/bot_name")
async def get_bot_name(model: TokenModel):
    loop = get_running_loop()
    future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        future.set_result(True)

    loop.create_task(bot.start(model.token))
    try:
        await wait_for(future, 5 * 60)
        name = bot.user.name
        await bot.close()
        return name
    except TimeoutError as err:
        await bot.close()
        raise err


@router.post("/listen_message")
async def listen_message(listener: Listener):
    loop = get_running_loop()
    future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_message(msg):
        if not msg.author.bot:
            if msg.channel.id == listener.channel_id:
                future.set_result(msg.content)

    loop.create_task(bot.start(listener.token))
    try:
        result = await wait_for(future, 5 * 60)
        await bot.close()
        return result
    except TimeoutError as err:
        await bot.close()
        raise err


@router.post("/channels/{channel_id}/react/{message_id}")
async def add_react_message(channel_id: int, message_id: str, model: ReactionModel):
    loop = get_running_loop()
    future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        future.set_result(True)

    loop.create_task(bot.start(model.token))
    try:
        result = await wait_for(future, 5 * 60)
        await bot.get_channel(channel_id).get_partial_message(message_id).add_reaction(model.emoji)
        await bot.close()
        return result
    except TimeoutError as err:
        await bot.close()
        raise err


@router.delete("/channels/{channel_id}/react/{message_id}")
async def delete_react_message(channel_id: int, message_id: str, model: ReactionModel):
    loop = get_running_loop()
    future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        future.set_result(True)

    loop.create_task(bot.start(model.token))
    try:
        result = await wait_for(future, 5 * 60)
        await bot.get_channel(channel_id).get_partial_message(message_id).remove_reaction(model.emoji, bot.user)
        await bot.close()
        return result
    except TimeoutError as err:
        await bot.close()
        raise err


@router.post("/channels/{channel_id}/mentions/last")
async def get_last_mention(channel_id: int, model: ChannelLastFileMessageModel):
    loop = get_running_loop()
    future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        future.set_result(True)

    loop.create_task(bot.start(model.token))
    try:
        result = await wait_for(future, 5 * 60)
        channel = bot.get_channel(channel_id)
        if channel:
            async for msg in channel.history(limit=model.limit):
                if not msg.author.bot:
                    if msg.content.find(f"<@{bot.user.id}>") != -1:
                        return Response(
                            dumps({"id": msg.id, "content": msg.content}), headers={"Content-Type": "application/json"}
                        )
        await bot.close()
        return result
    except TimeoutError as err:
        await bot.close()
        raise err


@router.post("/listen_mention")
async def listen_mention(listener: MentionListener):
    loop = get_running_loop()
    future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_message(msg: Message):
        import re

        if not msg.author.bot:
            mentioned = False
            for role in msg.role_mentions:
                if role.name == bot.user.name:
                    mentioned = True
            for user in msg.mentions:
                if user.id == bot.user.id:
                    mentioned = True
            if mentioned:
                msg.content = re.sub(r"<@&?[0-9]{17,20}>", "", msg.content)
                if not listener.channel_id and not listener.guild_id:
                    return future.set_result({"id": msg.id, "content": msg.content})
                if listener.channel_id and msg.channel.id == listener.channel_id:
                    return future.set_result({"id": msg.id, "content": msg.content})
                if listener.guild_id and msg.author.guild.id == listener.guild_id:
                    return future.set_result({"id": msg.id, "content": msg.content})

    loop.create_task(bot.start(listener.token))
    try:
        result = await wait_for(future, 5 * 60)
        await bot.close()
        return result
    except TimeoutError as err:
        await bot.close()
        raise err


def SendAudio(file_path: str, channel_id: int, token: str):
    import os
    import json
    import requests
    import sys
    import aiohttp

    with open(file_path, "rb") as file:
        audio_data, sample_rate = sf.read(file.name)
        duration = round(len(audio_data) / sample_rate, 1)
        characters = (
            " !#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}~Çüéâäàå"
        )
        random_string = "".join(random.choice(characters) for _ in range(64))
        waveform = base64.b64encode(random_string.encode("utf-8")).decode("utf-8")
    url = f"https://discord.com/api/v9/channels/{channel_id}/attachments"
    with open(file_path, "rb") as file:
        file.seek(0, os.SEEK_END)
        payload = json.dumps(
            {"files": [{"filename": os.path.basename(file.name), "file_size": file.tell(), "id": "261"}]}
        )
        headers = {
            "accept": "*/*",
            "authorization": "Bot " + token,
            "content-type": "application/json",
            "user-agent": "DiscordBot (https://github.com/Rapptz/discord.py 2.3.2) Python/{0[0]}.{0[1]} aiohttp/{1}".format(
                sys.version_info, aiohttp.__version__
            ),
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        response_data = response.json()
        if "attachments" in response_data:
            attachments = response_data["attachments"]
            attachments[0]["upload_url"]
            file.seek(0)
            payload = file.read()
            headers = {
                "authority": "discord-attachments-uploads-prd.storage.googleapis.com",
                "accept": "*/*",
                "content-type": "audio/ogg",
                "user-agent": "DiscordBot (https://github.com/Rapptz/discord.py 2.3.2) Python/{0[0]}.{0[1]} aiohttp/{1}".format(
                    sys.version_info, aiohttp.__version__
                ),
            }
            file.seek(0)

            response = requests.request("PUT", attachments[0]["upload_url"], headers=headers, data=payload)

            content = {
                "content": "",
                "channel_id": channel_id,
                "type": 0,
                "sticker_ids": [],
                "attachments": [
                    {
                        "content_type": "audio/ogg",
                        "duration_secs": duration,
                        "filename": "voice-message.ogg",
                        "id": channel_id,
                        "size": 4096,
                        "uploaded_filename": attachments[0]["upload_filename"],
                        "waveform": waveform,
                        "spoiler": False,
                        "sensitive": False,
                    }
                ],
                "flags": 8192,
            }

            headers = {
                "accept": "*/*",
                "authorization": "Bot " + token,
                "content-type": "application/json",
                "referer": f"https://discord.com/channels/^@me/{channel_id}",
                "user-agent": "DiscordBot (https://github.com/Rapptz/discord.py 2.3.2) Python/{0[0]}.{0[1]} aiohttp/{1}".format(
                    sys.version_info, aiohttp.__version__
                ),
            }
            response = requests.request(
                "POST",
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                headers=headers,
                data=dumps(content),
            )
        else:
            raise ValueError(f"Attachment URL returned {response_data}")


@router.post("/channels/{channel_id}/send_message")
async def send_message(channel_id: int, model: SendMessageModel):
    loop = get_running_loop()
    ready_future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        ready_future.set_result(True)

    loop.create_task(bot.start(model.token))
    try:
        ready = await wait_for(ready_future, 30)
        channel = bot.get_channel(channel_id)
        stickers = []
        file = None
        sent = False
        reference = None
        if model.filename:
            if model.filename.endswith(".txt"):
                file = File(io.StringIO(model.data["text"], filename=model.filename))
            elif model.is_audio:
                SendAudio(model.data["file_path"], channel_id, model.token)
                sent = True
            else:
                file = File(model.data["file_path"], filename=model.filename)
        if not sent:
            if model.sticker_id:
                stickers = [Sticker(id=model.sticker_id)]
            if model.reference:
                reference = channel.get_partial_message(model.reference)
            await channel.send(model.message, file=file, stickers=stickers, reference=reference)
        await bot.close()
        return ready
    except TimeoutError as err:
        await bot.close()
        raise err


@router.post("/guilds/{guild_id}/stickers")
async def get_stickers(guild_id: int, model: TokenModel):
    loop = get_running_loop()
    ready_future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        ready_future.set_result(True)

    loop.create_task(bot.start(model.token))
    try:
        await wait_for(ready_future, 30)
        guild = bot.get_guild(guild_id)
        if not guild:
            return Response("invalid GuildId", status_code=409)
        stickers = guild.fetch_stickers()
        stickers = [
            {
                "id": sticker.id,
                "name": sticker.name,
                "emoji": sticker.emoji,
                "url": sticker.url,
                "available": sticker.available,
            }
            for sticker in await stickers
        ]
        await bot.close()
        return Response(dumps(stickers), headers={"Content-Type": "application/json"})
    except TimeoutError as err:
        await bot.close()
        raise err


@router.post("/channels/{channel_id}/get_messages/last")
async def get_channel_messages_by_type(channel_id: int, model: ChannelByContentTypeMessageModel):
    loop = get_running_loop()
    ready_future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        ready_future.set_result(True)

    loop.create_task(bot.start(model.token))
    try:
        await wait_for(ready_future, 30)
        channel = bot.get_channel(channel_id)
        # Coleta as mensagens usando um loop assíncrono
        async for msg in channel.history(
            limit=model.limit if model.limit else None
        ):  # limit=None para obter todas as mensagens
            if msg.attachments:
                for attachment in msg.attachments:
                    if attachment.content_type and any(
                        [attachment.content_type.find(i) != -1 for i in model.content_type]
                    ):
                        file = {
                            "content_type": attachment.content_type,
                            "filename": attachment.filename,
                        }
                        file["content"] = base64.b64encode(await attachment.read()).decode("utf-8")
                        return Response(dumps(file), headers={"Content-Type": "application/json"})
        await bot.close()
        return Response(None, status_code=404, headers={"Content-Type": "application/json"})
    except TimeoutError as err:
        await bot.close()
        raise err


@router.post("/channels/{channel_id}/get_messages")
async def get_channel_messages(channel_id: int, model: ChannelMessagesModel):
    loop = get_running_loop()
    ready_future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        ready_future.set_result(True)

    loop.create_task(bot.start(model.token))
    try:
        await wait_for(ready_future, 30)
        channel = bot.get_channel(channel_id)
        messages = []
        # Coleta as mensagens usando um loop assíncrono
        async for msg in channel.history(
            limit=model.limit if model.limit else None
        ):  # limit=None para obter todas as mensagens
            name = msg.author.name
            nick = msg.author.nick if hasattr(msg.author, "nick") else None
            attachments = []
            if not model.ignore_attachments and msg.attachments:
                for attachment in msg.attachments:
                    file = {
                        "content_type": attachment.content_type,
                        "filename": attachment.filename,
                    }
                    if not model.ignore_file_content:
                        file["content"] = base64.b64encode(await attachment.read()).decode("utf-8")
                    with open(attachment.filename, "wb") as f:
                        decoded = base64.b64encode(await attachment.read()).decode("utf-8")
                        encoded = base64.b64decode(decoded)
                        f.write(encoded)
                    attachments.append(file)
            messages.append(
                {
                    "id": msg.id,
                    "author": {"id": msg.author.id, "name": name, "nick": nick},
                    "message": msg.content,
                    "attachments": attachments,
                }
            )
        messages = dumps(messages)
        await bot.close()
        return Response(messages, headers={"Content-Type": "application/json"})
    except TimeoutError as err:
        await bot.close()
        raise err


@router.post("/get_guild_users")
async def get_users_of_guild(message: GetGuildUsersModel):
    loop = get_running_loop()
    ready_future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        ready_future.set_result(True)

    loop.create_task(bot.start(message.token))
    try:
        await wait_for(ready_future, 30)
        if message.guild_id:
            guild = bot.get_guild(message.guild_id)
            await bot.close()
            if guild:
                return [
                    {
                        "id": member.id,
                        "name": member.name,
                        "nick": member.nick,
                        "roles": [str(role) for role in member.roles],
                        "status": member.status.value,
                        "activities": member.activities,
                        "banner": member.banner,
                        "pending": member.pending,
                        "avatar": member.avatar.url if member.avatar else None,
                    }
                    for member in guild.members
                ]
            return Response("invalid GuildId", status_code=409)
        if message.channel_id:
            channel = bot.get_channel(message.channel_id)
            await bot.close()

            if channel and channel.guild:
                return [
                    {
                        "id": member.id,
                        "name": member.name,
                        "nick": member.nick,
                        "roles": [str(role) for role in member.roles],
                        "status": member.status.value,
                        "activities": member.activities,
                        "banner": member.banner,
                        "pending": member.pending,
                        "avatar": member.avatar.url if member.avatar else None,
                    }
                    for member in channel.guild.members
                    if channel.permissions_for(member).read_messages
                ]
            return Response("invalid ChannelId", status_code=409)

    except TimeoutError as err:
        await bot.close()
        raise err


@router.post("/guilds")
async def get_guilds(model: TokenModel):
    loop = get_running_loop()
    ready_future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        ready_future.set_result(True)

    loop.create_task(bot.start(model.token))
    try:
        bot.fetch_guilds
        await wait_for(ready_future, 30)
        guilds = [
            {
                "id": guild.id,
                "name": guild.name,
                "description": guild.description,
                "members_count": len(guild.members),
                "members": [
                    {
                        "id": member.id,
                        "name": member.name,
                        "nick": member.nick,
                        "roles": [str(role) for role in member.roles],
                        "status": member.status.value,
                        "activities": member.activities,
                        "banner": member.banner,
                        "pending": member.pending,
                        "avatar": member.avatar.url if member.avatar else None,
                    }
                    for member in guild.members
                ],
            }
            for guild in bot.guilds
        ]
        return Response(dumps(guilds), headers={"Content-Type": "application/json"})
    except TimeoutError as err:
        await bot.close()
        raise err


@router.post("/guilds/{guild_id}/get_channels")
async def get_guild_channels(guild_id: int, model: GetGuildChannelsModel):
    loop = get_running_loop()
    ready_future = Future(loop=loop)
    bot = commands.Bot(command_prefix="!", intents=Intents.all())

    @bot.event
    async def on_ready():
        ready_future.set_result(True)

    loop.create_task(bot.start(model.token))
    try:
        _ = await wait_for(ready_future, 30)
        guild = bot.get_guild(guild_id)
        if not guild:
            return Response("invalid GuildId", status_code=409)
        resp = [
            {"id": channel.id, "name": channel.name, "type": channel.__class__.__name__.replace("Channel", "")}
            for channel in guild.channels
        ]
        if model.type:
            resp = [item for item in resp if item["type"] == model.type]
        await bot.close()
        return Response(dumps(resp), headers={"Content-Type": "application/json"})
    except TimeoutError as err:
        await bot.close()
        raise err
