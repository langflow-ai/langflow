import json
import re

from google_auth_oauthlib.flow import InstalledAppFlow
from lfx.custom.custom_component.component import Component
from lfx.io import FileInput, MultilineInput, Output
from lfx.schema.data import Data

_SCOPE = (
    r"(?:https://www\.googleapis\.com/auth/[\w.\-]+"
    r"|mail\.google\.com/"
    r"|www\.google\.com/calendar/feeds"
    r"|www\.google\.com/m8/feeds)"
)
_SCOPE_LIST_PATTERN = re.compile(rf"{_SCOPE}(?:,\s*{_SCOPE})*")
_OAUTH_CALLBACK_TIMEOUT_SECONDS = 300


class GoogleOAuthToken(Component):
    display_name = "Google OAuth Token"
    description = "Generates a JSON string with your Google OAuth token."
    documentation: str = "https://developers.google.com/identity/protocols/oauth2/web-server?hl=pt-br#python_1"
    icon = "Google"
    name = "GoogleOAuthToken"
    legacy: bool = True
    inputs = [
        MultilineInput(
            name="scopes",
            display_name="Scopes",
            info="Input scopes for your application.",
            required=True,
        ),
        FileInput(
            name="oauth_credentials",
            display_name="Credentials File",
            info="Input OAuth Credentials file (e.g. credentials.json).",
            file_types=["json"],
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def validate_scopes(self, scopes: str) -> None:
        if _SCOPE_LIST_PATTERN.fullmatch(scopes) is None:
            error_message = "Invalid scope format."
            raise ValueError(error_message)

    def build_output(self) -> Data:
        self.validate_scopes(self.scopes)

        user_scopes = [scope.strip() for scope in self.scopes.split(",")]
        if self.scopes:
            scopes = user_scopes
        else:
            error_message = "Incorrect scope, check the scopes field."
            raise ValueError(error_message)

        if not self.oauth_credentials:
            error_message = "OAuth 2.0 Credentials file not provided."
            raise ValueError(error_message)

        try:
            flow = InstalledAppFlow.from_client_secrets_file(self.oauth_credentials, scopes)
            creds = flow.run_local_server(port=0, timeout_seconds=_OAUTH_CALLBACK_TIMEOUT_SECONDS)
            creds_json = json.loads(creds.to_json())
        except Exception as e:
            msg = f"OAuth authorization failed: {e}"
            raise ValueError(msg) from e

        return Data(data=creds_json)
