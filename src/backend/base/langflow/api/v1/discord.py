from typing import Optional, Dict, Any
from pydantic import BaseModel, model_validator
from fastapi import APIRouter, Response
from asyncio import get_running_loop, Future, wait_for
from discord.ext import commands
from discord import Intents, File, Sticker
from json import dumps
import base64
import io


router = APIRouter(tags=["Discord"])


class TokenModel(BaseModel):
    token: str


class ChannelMessagesModel(TokenModel):
    limit: int = 20
    timeout: int = 5 * 60
    ignore_file_content: bool = True
    ignore_attachments: bool = True


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


class SendMessageModel(TokenModel):
    message: Optional[str] = None
    sticker_id: Optional[str] = None
    filename: Optional[str] = None
    type: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


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


"""@router.post("/channels/{channel_id}/send_message")
async def get_message(channel_id: int, model: SendMessageModel):
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
        await channel.send(model.message)
        await bot.close()
        return ready
    except TimeoutError as err:
        await bot.close()
        raise err"""


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
        if model.filename:
            if model.filename.endswith(".txt"):
                file = File(io.StringIO(model.data["text"], filename=model.filename))
            else:
                file = File(model.data["file_path"], filename=model.filename)
        if model.sticker_id:
            stickers = [Sticker(id=model.sticker_id)]
        await channel.send(model.message, file=file, stickers=stickers)
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
                        file["content"] = (base64.b64encode((await attachment.read())).decode("utf-8"),)
                    attachments.append(file)
            messages.append(
                {
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
