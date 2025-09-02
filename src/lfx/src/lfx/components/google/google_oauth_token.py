import json
import re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from lfx.custom.custom_component.component import Component
from lfx.io import FileInput, MultilineInput, Output
from lfx.schema.data import Data


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

    def validate_scopes(self, scopes):
        pattern = (
            r"^(https://www\.googleapis\.com/auth/[\w\.\-]+"
            r"|mail\.google\.com/"
            r"|www\.google\.com/calendar/feeds"
            r"|www\.google\.com/m8/feeds)"
            r"(,\s*https://www\.googleapis\.com/auth/[\w\.\-]+"
            r"|mail\.google\.com/"
            r"|www\.google\.com/calendar/feeds"
            r"|www\.google\.com/m8/feeds)*$"
        )
        if not re.match(pattern, scopes):
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

        creds = None
        token_path = Path("token.json")

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if self.oauth_credentials:
                    client_secret_file = self.oauth_credentials
                else:
                    error_message = "OAuth 2.0 Credentials file not provided."
                    raise ValueError(error_message)

                flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes)
                creds = flow.run_local_server(port=0)

                token_path.write_text(creds.to_json(), encoding="utf-8")

        creds_json = json.loads(creds.to_json())

        return Data(data=creds_json)
