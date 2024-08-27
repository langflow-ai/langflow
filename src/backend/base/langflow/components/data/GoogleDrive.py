import json
from pathlib import Path
from typing import Optional, Any
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError

from langflow.base.data.utils import CustomUnstructuredFileLoader
from langflow.custom import Component
from langflow.inputs import MessageTextInput, FileInput
from langflow.io import SecretStrInput
from langflow.template import Output
from langflow.schema import Data
from langchain_google_community import GoogleDriveLoader
from langflow.helpers.data import docs_to_data

from json.decoder import JSONDecodeError


class GoogleDriveComponent(Component):
    display_name = "Google Drive Loader"
    description = "Loads documents from Google Drive using provided credentials."
    icon = "Google"

    inputs = [
        SecretStrInput(
            name="json_string",
            display_name="OAuth 2.0 JSON Token Info",
            info="JSON string containing OAuth 2.0 access token information for service account access",
        ),
        FileInput(
            name="service_account_credentials",
            display_name="Service Account Credentials",
            info="JSON credentials file. Leave empty to fallback to environment variables",
            file_types=["json"],
        ),

        MessageTextInput(
            name="document_id", display_name="Document ID", info="Single Google Drive document ID to read from"
        ),
        MessageTextInput(
            name="folder_id", display_name="Folder ID", info="Google Drive Folder ID to read recursively from"
        ),
    ]

    outputs = [
        Output(display_name="Loaded Documents", name="docs", method="load_documents"),
    ]

    def load_documents(self) -> Data:
        class CustomGoogleDriveLoader(GoogleDriveLoader):
            creds: Optional[Any] = None
            """Credentials object to be passed directly."""

            def _load_credentials(self):
                """Load credentials from the provided creds attribute or fallback to the original method."""
                if self.creds:
                    return self.creds
                else:
                    raise ValueError("No credentials provided.")

            class Config:
                arbitrary_types_allowed = True

        if self.service_account_credentials and self.json_string:
            raise ValueError("Both service account credentials and JSON string cannot be provided")

        if self.document_id and self.folder_id:
            raise ValueError("Both document ID and folder ID cannot be provided")



        doc_args = {
            "file_loader_cls": CustomUnstructuredFileLoader
        }
        if self.document_id:
            doc_args["document_ids"] = [self.document_id]
        elif self.folder_id:
            doc_args["folder_id"] = self.folder_id
            doc_args["recursive"] = True
        else:
            raise ValueError("Either document ID or folder ID must be provided")

        if self.service_account_credentials:
            loader = GoogleDriveLoader(
                service_account_key=Path(self.service_account_credentials), **doc_args)
        elif self.json_string:
            try:
                token_info = json.loads(self.json_string)
            except JSONDecodeError as e:
                print(e)
                raise ValueError("Invalid JSON string: " + str(e)) from e
            creds = Credentials.from_authorized_user_info(token_info)
            loader = CustomGoogleDriveLoader(
                creds=creds, **doc_args
            )
        else:
            raise ValueError("Either service account credentials or JSON string must be provided")
        try:
            docs = loader.load()
        # catch google.auth.exceptions.RefreshError
        except RefreshError as e:
            raise ValueError(
                "Authentication error: Unable to refresh authentication token. Please try to reauthenticate."
            ) from e
        except Exception as e:
            raise ValueError(f"Error loading documents: {e}") from e

        data = docs_to_data(docs)
        self.status = data
        return Data(data={"text": data})
