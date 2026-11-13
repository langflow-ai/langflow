"""List the posts of a profile on a social platform with SocialScrape."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from lfx_bundles.socialscrape.socialscrape_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    SocialScrapeAPIError,
    bare_handle,
    socialscrape_request,
)

POSTS_PLATFORMS = ["instagram", "tiktok", "threads", "bluesky", "truthsocial"]


class SocialScrapePostsComponent(Component):
    """List one page of an account's posts through SocialScrape.

    Each run returns one page. Pass the cursor from the **Page Info** output back into
    the **Cursor** input to read the next page; every page costs credits.
    """

    display_name = "SocialScrape Posts"
    description = "List the posts of a profile on Instagram, TikTok, Threads, Bluesky and Truth Social."
    documentation = DOCUMENTATION_URL
    icon = "Share2"
    name = "SocialScrapePosts"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="SocialScrape API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        DropdownInput(
            name="platform",
            display_name="Platform",
            info="The platform the account is on. TikTok lists the account's videos.",
            options=POSTS_PLATFORMS,
            value="instagram",
            tool_mode=True,
        ),
        MessageTextInput(
            name="handle",
            display_name="Handle",
            info="The account handle, with or without a leading @.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="cursor",
            display_name="Cursor",
            info="The cursor from a previous run's Page Info, to read the next page. Leave empty for the first page.",
            advanced=True,
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for SocialScrape to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Posts", name="posts", method="get_posts"),
        Output(display_name="Page Info", name="page_info", method="get_page_info"),
    ]

    def _fetch_page(self) -> dict[str, Any]:
        """Fetch the page once per run; both outputs read the same answer.

        The answer is kept only for the inputs it was fetched with, so a component
        that runs again with another handle, platform or cursor fetches again.
        """
        platform = str(self.platform or "").strip().lower()
        if platform not in POSTS_PLATFORMS:
            msg = f"Choose a platform from: {', '.join(POSTS_PLATFORMS)}; got {platform!r}."
            raise SocialScrapeAPIError(msg)
        handle = bare_handle(self.handle)
        cursor = str(self.cursor or "").strip()
        key = (platform, handle, cursor)
        if getattr(self, "_page_key", None) == key:
            return self._page
        # TikTok publishes videos only, so its list lives under /profile/videos.
        listing = "videos" if platform == "tiktok" else "posts"
        data = socialscrape_request(
            f"/v1/{platform}/profile/{listing}",
            api_key=self.api_key,
            timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
            params={"handle": handle, "cursor": cursor},
        )
        if not isinstance(data.get("items"), list):
            msg = "SocialScrape API returned a posts answer without a list of items."
            raise SocialScrapeAPIError(msg)
        self._page = data
        self._page_key = key
        return data

    def get_posts(self) -> DataFrame:
        """Return one row per post, with the post text as ``text``."""
        try:
            page = self._fetch_page()
        except SocialScrapeAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return DataFrame([Data(text=str(exc), data={"error": str(exc)})])
        posts = [Data(text=str(item.get("text") or ""), data=item) for item in page["items"] if isinstance(item, dict)]
        self.status = posts
        return DataFrame(posts)

    def get_page_info(self) -> Data:
        """Return the ``cursor`` for the next page and whether ``has_more`` pages exist."""
        try:
            page = self._fetch_page()
        except SocialScrapeAPIError as exc:
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})
        info = Data(data={"cursor": page.get("cursor"), "has_more": bool(page.get("has_more"))})
        self.status = info
        return info
