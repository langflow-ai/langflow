"""Upload-Post: publish a video to several social platforms at once."""

from __future__ import annotations

from typing import Any

from lfx.io import DropdownInput, FileInput, MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data  # noqa: TC002 - output type is read from the annotation at runtime
from lfx_uploadpost._base import (
    UploadPostBaseComponent,
    api_key_input,
    platforms_input,
    publishing_inputs,
    user_input,
)
from lfx_uploadpost._client import TIKTOK_PRIVACY, VIDEO_PLATFORMS, YOUTUBE_PRIVACY

VIDEO_FILE_TYPES = ["mp4", "mov", "webm", "m4v", "avi", "mkv"]


class UploadPostVideoComponent(UploadPostBaseComponent):
    display_name = "Upload-Post Publish Video"
    description = (
        "Publish a video to TikTok, Instagram, YouTube, LinkedIn, Facebook, X, Threads, Pinterest and Bluesky "
        "in one call with Upload-Post."
    )
    name = "UploadPostVideo"
    endpoint = "/api/upload"

    inputs = [
        api_key_input(),
        user_input(),
        platforms_input(VIDEO_PLATFORMS, ["tiktok", "instagram", "youtube"]),
        FileInput(
            name="video_file",
            display_name="Video File",
            file_types=VIDEO_FILE_TYPES,
            info="The video to publish. Alternatively, set Video URL.",
        ),
        MessageTextInput(
            name="video_url",
            display_name="Video URL",
            info="Public URL of the video to publish, used when no Video File is set.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="title",
            display_name="Title / Caption",
            required=True,
            info="Caption on TikTok, Instagram, X and Threads; title on YouTube (max 100 characters there).",
            tool_mode=True,
        ),
        MultilineInput(
            name="description",
            display_name="Description",
            info="Longer text used on YouTube, LinkedIn, Facebook and Pinterest.",
            tool_mode=True,
        ),
        DropdownInput(
            name="youtube_privacy",
            display_name="YouTube Privacy",
            options=YOUTUBE_PRIVACY,
            value="private",
            advanced=True,
            info="Visibility of the YouTube upload. Defaults to private so nothing goes public by accident.",
        ),
        DropdownInput(
            name="tiktok_privacy",
            display_name="TikTok Privacy",
            options=TIKTOK_PRIVACY,
            value="account default",
            advanced=True,
            info="TikTok privacy level. 'account default' keeps the account's own setting.",
        ),
        *publishing_inputs(),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.
        Output(display_name="Result", name="result", method="upload_post_publish_video"),
    ]

    def build_request(self) -> tuple[dict[str, Any], list[tuple[str, str]]]:
        title = self._text("title")
        if not title:
            msg = "Title / Caption is required."
            raise ValueError(msg)
        fields = self._common_fields()
        fields["title"] = title
        if self._text("description"):
            fields["description"] = self._text("description")
        platforms = fields["platform[]"]
        if "youtube" in platforms:
            if len(title) > 100:  # noqa: PLR2004 - YouTube's title limit
                msg = f"The title is {len(title)} characters; YouTube allows 100."
                raise ValueError(msg)
            fields["privacyStatus"] = self.youtube_privacy or "private"
        if "tiktok" in platforms and self.tiktok_privacy and self.tiktok_privacy != "account default":
            fields["privacy_level"] = self.tiktok_privacy

        if self.video_file:
            return fields, [("video", self._local_file(self.video_file))]
        if self._text("video_url"):
            fields["video"] = self._text("video_url")
            return fields, []
        msg = "Set a Video File or a Video URL."
        raise ValueError(msg)

    def upload_post_publish_video(self) -> Data:
        return self.publish()
