from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, MultilineInput, SecretStrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output
from lfx_publora.components.publora._publora_api import PubloraAPIError, publora_request


def _split_list(value: str | None) -> list[str]:
    """Split a comma- or newline-separated string into trimmed, de-duplicated items."""
    if not value:
        return []
    items: list[str] = []
    for part in value.replace("\n", ",").split(","):
        item = part.strip()
        if item and item not in items:
            items.append(item)
    return items


class PubloraCreatePostComponent(Component):
    """Create a draft or a scheduled post through Publora."""

    display_name = "Publora Create Post"
    description = (
        "Create a social media post in Publora for LinkedIn, X, Instagram, Threads, TikTok, YouTube, "
        "Facebook, Bluesky, Mastodon or Telegram. Without a scheduled time the post stays a draft."
    )
    documentation = "https://docs.publora.com/endpoints/create-post"
    icon = "send"

    inputs = [
        MultilineInput(
            name="content",
            display_name="Content",
            required=True,
            info="The text of the post.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="platforms",
            display_name="Platforms",
            required=True,
            info=(
                "Comma-separated platformId values to post to, for example 'linkedin-ABC123, bluesky-did:plc:xyz'. "
                "Get them from the Publora List Connections component."
            ),
            tool_mode=True,
        ),
        MessageTextInput(
            name="scheduled_time",
            display_name="Scheduled Time",
            required=False,
            info="ISO 8601 UTC time to publish, for example '2026-10-14T09:00:00Z'. Leave empty to keep a draft.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="media_urls",
            display_name="Media URLs",
            required=False,
            advanced=True,
            info=(
                "Comma-separated public https URLs of images or videos to attach. "
                "Instagram, TikTok and YouTube need media before a post can be scheduled."
            ),
        ),
        SecretStrInput(
            name="publora_api_key",
            display_name="Publora API Key",
            required=True,
            info="Your Publora API key, from the API page of your Publora dashboard (app.publora.com/dashboard/api).",
            password=True,
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode; keep it product-specific.
        Output(display_name="Post", name="post", method="publora_create_post"),
    ]

    def _request_body(self) -> dict:
        """Build the JSON body for POST /create-post."""
        body: dict = {"content": self.content or "", "platforms": _split_list(self.platforms)}
        scheduled_time = self.scheduled_time.strip() if isinstance(self.scheduled_time, str) else ""
        if scheduled_time:
            body["scheduledTime"] = scheduled_time
        media_urls = _split_list(self.media_urls)
        if media_urls:
            body["mediaUrls"] = media_urls
        return body

    def _error_result(self, message: str) -> Data:
        error_data = Data(text=message, data={"error": message})
        self.status = error_data
        return error_data

    def publora_create_post(self) -> Data:
        """Create the post and return its postGroupId and stored scheduledTime."""
        body = self._request_body()
        if not body["platforms"]:
            return self._error_result("At least one platformId is required in Platforms.")

        try:
            payload = publora_request("POST", "/create-post", self.publora_api_key, json=body)
        except PubloraAPIError as e:
            return self._error_result(str(e))

        scheduled = payload.get("scheduledTime")
        result = {
            "postGroupId": payload.get("postGroupId"),
            "scheduledTime": scheduled,
            "status": "scheduled" if scheduled else "draft",
            "warnings": payload.get("warnings") or [],
        }
        when = f"scheduled for {scheduled}" if scheduled else "saved as a draft"
        data = Data(text=f"Publora post {result['postGroupId']} {when}.", data=result)
        self.status = data
        return data
