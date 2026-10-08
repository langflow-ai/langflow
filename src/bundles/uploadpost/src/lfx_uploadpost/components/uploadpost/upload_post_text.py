"""Upload-Post: publish a text post to several platforms."""

from __future__ import annotations

from typing import Any

from lfx.io import MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data  # noqa: TC002 - output type is read from the annotation at runtime
from lfx_uploadpost._base import (
    UploadPostBaseComponent,
    api_key_input,
    platforms_input,
    publishing_inputs,
    user_input,
)
from lfx_uploadpost._client import TEXT_PLATFORMS


class UploadPostTextComponent(UploadPostBaseComponent):
    display_name = "Upload-Post Publish Text"
    description = "Publish a text post to X, LinkedIn, Facebook, Threads and Bluesky in one call with Upload-Post."
    name = "UploadPostText"
    endpoint = "/api/upload_text"

    inputs = [
        api_key_input(),
        user_input(),
        platforms_input(TEXT_PLATFORMS, ["x", "linkedin"]),
        MultilineInput(
            name="text",
            display_name="Text",
            required=True,
            info="The post text.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="link_url",
            display_name="Link URL",
            advanced=True,
            info="Optional URL shown as a link preview card on LinkedIn, Bluesky and Facebook.",
        ),
        *[i for i in publishing_inputs() if i.name != "pinterest_board_id"],
    ]

    outputs = [
        Output(display_name="Result", name="result", method="upload_post_publish_text"),
    ]

    def build_request(self) -> tuple[dict[str, Any], list[tuple[str, str]]]:
        text = self._text("text")
        if not text:
            msg = "Text is required."
            raise ValueError(msg)
        fields = self._common_fields()
        fields["title"] = text
        if self._text("link_url"):
            fields["link_url"] = self._text("link_url")
        return fields, []

    def upload_post_publish_text(self) -> Data:
        return self.publish()
