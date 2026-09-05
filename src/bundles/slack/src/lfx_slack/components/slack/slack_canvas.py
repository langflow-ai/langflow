"""Slack: Create Canvas (as user) -- Web API ``canvases.create``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.io import MultilineInput, Output, StrInput
from lfx.schema.data import Data

from lfx_slack._base import USER_IDENTITY, SlackBaseComponent, user_connection_input

if TYPE_CHECKING:
    from lfx_slack._client import SlackClient

CAPABILITY_ID = "slack.user.canvas"
API_METHOD = "canvases_create"

# canvases.create accepts a markdown document_content up to 1 MiB.
MAX_MARKDOWN_BYTES = 1024 * 1024


class SlackCanvasComponent(SlackBaseComponent):
    display_name = "Slack: Create Canvas (as user)"
    description = "Create a Slack canvas owned by the connected user from markdown."
    name = "SlackCanvas"

    capability_id = CAPABILITY_ID
    slack_identity = USER_IDENTITY

    inputs = [
        user_connection_input(capability=CAPABILITY_ID, required_scopes=["canvases:write"]),
        StrInput(
            name="title",
            display_name="Title",
            info="Optional canvas title.",
        ),
        MultilineInput(
            name="markdown",
            display_name="Markdown",
            required=True,
            info="Canvas body as markdown. Slack accepts up to 1 MiB.",
        ),
        StrInput(
            name="channel_id",
            display_name="Channel ID",
            info="Creates a channel canvas instead of a standalone one. Required on free Slack plans.",
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Canvas", name="canvas", method="build_canvas")]

    async def build_canvas(self) -> Data:
        """Create the canvas and return its id."""
        markdown = self.markdown or ""
        if not markdown:
            msg = "Markdown is required."
            raise ValueError(msg)
        size = len(markdown.encode("utf-8"))
        if size > MAX_MARKDOWN_BYTES:
            msg = f"Canvas markdown is {size} bytes; Slack accepts up to {MAX_MARKDOWN_BYTES}."
            raise ValueError(msg)

        request = {"document_content": {"type": "markdown", "markdown": markdown}}
        title = (self.title or "").strip()
        if title:
            request["title"] = title
        channel_id = (self.channel_id or "").strip()
        if channel_id:
            request["channel_id"] = channel_id

        async def call(client: SlackClient) -> dict:
            return await client.call(API_METHOD, **request)

        body = await self.run_action(call)
        canvas_id = body.get("canvas_id")
        self.status = f"Created canvas {canvas_id}"
        return Data(data={"canvas_id": canvas_id, "channel_id": channel_id or None, "title": title or None})
