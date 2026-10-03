"""Upload-Post: publish one or more photos (or a carousel) to several platforms."""

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
from lfx_uploadpost._client import PHOTO_PLATFORMS, TIKTOK_PRIVACY

PHOTO_FILE_TYPES = ["jpg", "jpeg", "png", "webp", "gif"]


class UploadPostPhotosComponent(UploadPostBaseComponent):
    display_name = "Upload-Post Publish Photos"
    description = (
        "Publish photos or a carousel to TikTok, Instagram, LinkedIn, Facebook, X, Threads, Pinterest and Bluesky "
        "in one call with Upload-Post."
    )
    name = "UploadPostPhotos"
    endpoint = "/api/upload_photos"

    inputs = [
        api_key_input(),
        user_input(),
        platforms_input(PHOTO_PLATFORMS, ["instagram", "linkedin"]),
        FileInput(
            name="photo_files",
            display_name="Photo Files",
            file_types=PHOTO_FILE_TYPES,
            is_list=True,
            info="Photos to publish; several make a carousel. Alternatively, set Photo URLs.",
        ),
        MessageTextInput(
            name="photo_urls",
            display_name="Photo URLs",
            is_list=True,
            info="Public URLs of the photos, used when no Photo Files are set.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="title",
            display_name="Title / Caption",
            info="Caption of the post.",
            tool_mode=True,
        ),
        MultilineInput(
            name="description",
            display_name="Description",
            info="Longer text used on TikTok photo posts, LinkedIn, Facebook and Pinterest.",
            tool_mode=True,
        ),
        DropdownInput(
            name="tiktok_privacy",
            display_name="TikTok Privacy",
            options=TIKTOK_PRIVACY,
            value="account default",
            advanced=True,
            info="TikTok privacy level. 'account default' lets Upload-Post pick the default.",
        ),
        *publishing_inputs(),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="upload_post_publish_photos"),
    ]

    def build_request(self) -> tuple[dict[str, Any], list[tuple[str, str]]]:
        fields = self._common_fields()
        if self._text("title"):
            fields["title"] = self._text("title")
        if self._text("description"):
            fields["description"] = self._text("description")
        if "tiktok" in fields["platform[]"] and self.tiktok_privacy and self.tiktok_privacy != "account default":
            fields["privacy_level"] = self.tiktok_privacy

        files = self.photo_files if isinstance(self.photo_files, list) else [self.photo_files]
        files = [f for f in files if f]
        if files:
            return fields, [("photos[]", self._local_file(f)) for f in files]
        urls = self.photo_urls if isinstance(self.photo_urls, list) else [self.photo_urls]
        urls = [u.strip() for u in urls if isinstance(u, str) and u.strip()]
        if urls:
            fields["photos[]"] = urls
            return fields, []
        msg = "Set Photo Files or Photo URLs."
        raise ValueError(msg)

    def upload_post_publish_photos(self) -> Data:
        return self.publish()
