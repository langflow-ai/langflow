"""Get a profile on a social platform with SocialScrape."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.socialscrape.socialscrape_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    SocialScrapeAPIError,
    bare_handle,
    socialscrape_request,
)

PROFILE_PLATFORMS = ["instagram", "tiktok", "twitter", "threads", "bluesky", "snapchat", "twitch", "truthsocial"]


class SocialScrapeProfileComponent(Component):
    """Fetch one account's profile through SocialScrape."""

    display_name = "SocialScrape Profile"
    description = "Get a profile's name, bio, verification and follower counts on Instagram, TikTok, X and more."
    documentation = DOCUMENTATION_URL
    icon = "Share2"
    name = "SocialScrapeProfile"

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
            info="The platform the account is on.",
            options=PROFILE_PLATFORMS,
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
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for SocialScrape to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Profile", name="profile", method="get_profile"),
    ]

    def get_profile(self) -> Data:
        """Return the profile as one ``Data``; the bio is the ``text``."""
        try:
            platform = str(self.platform or "").strip().lower()
            if platform not in PROFILE_PLATFORMS:
                msg = f"Choose a platform from: {', '.join(PROFILE_PLATFORMS)}; got {platform!r}."
                raise SocialScrapeAPIError(msg)
            data = socialscrape_request(
                f"/v1/{platform}/profile",
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                params={"handle": bare_handle(self.handle)},
            )
        except SocialScrapeAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        profile = Data(text=str(data.get("bio") or data.get("name") or ""), data=data)
        self.status = profile
        return profile
