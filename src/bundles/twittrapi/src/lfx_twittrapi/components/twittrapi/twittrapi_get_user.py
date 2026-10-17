import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.schema.data import Data
from lfx.template.field.base import Output
from lfx_twittrapi.components.twittrapi._common import (
    TwittrAPIError,
    api_key_input,
    error_data,
    get_json,
    normalize_username,
    user_to_data,
)


class TwittrAPIGetUserComponent(Component):
    """Look up an X (Twitter) profile by username."""

    display_name = "TwittrAPI Get User"
    description = "Get an X (Twitter) user profile by username: bio, follower counts, verification and user ID."
    documentation = "https://www.twittrapi.com/docs/reference/user-by-username-username"
    icon = "TwittrAPI"

    inputs = [
        MessageTextInput(
            name="username",
            display_name="Username",
            required=True,
            tool_mode=True,
            info="X handle, with or without @, for example 'jack'.",
        ),
        api_key_input(),
    ]

    outputs = [
        Output(display_name="JSON", name="data", method="twittrapi_get_user"),
    ]

    def twittrapi_get_user(self) -> Data:
        """Return the profile as one Data object, or an error Data."""
        try:
            username = normalize_username(self.username)
            payload = get_json(self.twittrapi_api_key, f"/user/by/username/{username}")
        except httpx.HTTPError as e:
            result = error_data(f"TwittrAPI request failed: {e}")
        except (TwittrAPIError, ValueError) as e:
            result = error_data(str(e))
        else:
            user = payload.get("data")
            result = user_to_data(user) if isinstance(user, dict) else error_data(f"User @{username} not found.")
        self.status = result
        return result
