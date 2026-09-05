import json
import re
import warnings

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


_DEPRECATION_MESSAGE = (
    "GoogleOAuthToken is deprecated. It runs a local-server OAuth flow and hands a long-lived "
    "token to the flow, which cannot work on a server deployment and stores credentials in flow "
    "data. Use a managed Google connection with the Gmail, Drive and Calendar action components "
    "instead: https://docs.langflow.org/connection-oauth"
)

# Class names of the connection-backed components that replace this one. Kept as
# bundle-qualified references so the palette's replacement hint resolves.
_REPLACEMENTS = [
    "google.GmailSendComponent",
    "google.GoogleDriveListComponent",
    "google.GoogleDriveFetchComponent",
    "google.GoogleCalendarListComponent",
    "google.GoogleCalendarCreateComponent",
]


class GoogleOAuthToken(Component):
    """Deprecated local-server OAuth helper, superseded by managed connections (INT-10)."""

    display_name = "Google OAuth Token"
    description = (
        "Deprecated. Generates a JSON string with your Google OAuth token. Use a managed Google connection instead."
    )
    documentation: str = "https://docs.langflow.org/connection-oauth"
    icon = "Google"
    name = "GoogleOAuthToken"
    legacy: bool = True
    replacement = _REPLACEMENTS
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
        # Additive, non-fatal: existing flows keep working, but every run says
        # loudly that this path is going away.
        warnings.warn(_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)
        self.log(_DEPRECATION_MESSAGE, name="Deprecation")

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
