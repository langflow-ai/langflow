from langflow.custom import Component
from langflow.io import FileInput, Output
from langflow.schema import Data
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request  # Importação corrigida
import json
import os
import re


class GoogleOAuthToken(Component):
    display_name = "Google OAuth Token "
    description = "A component to generate a json string containing your Google OAuth token."
    documentation: str = "https://developers.google.com/identity/protocols/oauth2/web-server?hl=pt-br#python_1"
    icon = "Google"
    name = "GoogleOAuthToken"

    inputs = [
        StrInput(
            name="scopes",
            display_name="Scopes",
            info="Input a comma-separated list of scopes with the permissions required for your application.",
            required=True
        ),
        FileInput(
            name="oauth_credentials",
            display_name="Credentials File",
            info="Input OAuth Credentials file. (e.g. credentials.json)",
            file_types=["json"],
            required=True
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def validate_scopes(self, scopes):
        pattern = (
            r"^(https:\/\/(www\.googleapis\.com\/auth\/[\w\.\-]+"
            r"|mail\.google\.com\/"
            r"|www\.google\.com\/calendar\/feeds"
            r"|www\.google\.com\/m8\/feeds))"
            r"(,\s*https:\/\/(www\.googleapis\.com\/auth\/[\w\.\-]+"
            r"|mail\.google\.com\/"
            r"|www\.google\.com\/calendar\/feeds"
            r"|www\.google\.com\/m8\/feeds))*$"
        )
        if not re.match(pattern, scopes):
            raise ValueError(
                "Invalid format for scopes. Please ensure scopes are comma-separated, without quotes, and without extra characters. Also, check if each URL is correct."
            )

    def build_output(self) -> Data:
        self.validate_scopes(self.scopes)


        user_scopes = [scope.strip() for scope in self.scopes.split(',')]
        if self.scopes:
            SCOPES = user_scopes    
        else:
            raise ValueError("Incorrect Scope, check if you filled in the scopes field correctly!")

        creds = None
        token_path = 'token.json' 

        if os.path.exists(token_path):
            with open(token_path, 'r') as token_file:
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if self.oauth_credentials:
                    CLIENT_SECRET_FILE = self.oauth_credentials
                else:
                    raise ValueError("Oauth 2.0 Credentials file not provided. (e.g. the credentials.json)")
                
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())

        return creds.to_json()
