import json
from json.decoder import JSONDecodeError

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from langchain_google_community import GoogleDriveLoader

from langflow.custom.custom_component.component import Component
from langflow.helpers.data import docs_to_data
from langflow.inputs.inputs import MessageTextInput
from langflow.io import SecretStrInput
from langflow.schema.data import Data
from langflow.template.field.base import Output


class GoogleDriveComponent(Component):
    display_name = "Google Drive Loader"
    description = "Loads documents from Google Drive using provided credentials."
    icon = "Google"
    legacy: bool = True

    inputs = [
        SecretStrInput(
            name="json_string",
            display_name="JSON String of the Service Account Token",
            info="JSON string containing OAuth 2.0 access token information for service account access",
            required=True,
        ),
        MessageTextInput(
            name="document_id", display_name="Document ID", info="Single Google Drive document ID", required=True
        ),
    ]

    outputs = [
        Output(display_name="Loaded Documents", name="docs", method="load_documents"),
    ]

    def load_documents(self) -> Data:
        class CustomGoogleDriveLoader(GoogleDriveLoader):
            creds: Credentials | None = None
            """Credentials object to be passed directly."""

            def _load_credentials(self):
                """Load credentials from the provided creds attribute or fallback to the original method."""
                if self.creds:
                    return self.creds
                msg = "No credentials provided."
                raise ValueError(msg)

            class Config:
                arbitrary_types_allowed = True

        json_string = self.json_string

        document_ids = [self.document_id]
        if len(document_ids) != 1:
            msg = "Expected a single document ID"
            raise ValueError(msg)

        # TODO: Add validation to check if the document ID is valid

        # Load the token information from the JSON string
        try:
            token_info = json.loads(json_string)
        except JSONDecodeError as e:
            msg = "Invalid JSON string"
            raise ValueError(msg) from e

        # Initialize the custom loader with the provided credentials and document IDs
        loader = CustomGoogleDriveLoader(
            creds=Credentials.from_authorized_user_info(token_info), document_ids=document_ids
        )

        # Load the documents
        try:
            docs = loader.load()
        # catch google.auth.exceptions.RefreshError
        except RefreshError as e:
            msg = "Authentication error: Unable to refresh authentication token. Please try to reauthenticate."
            raise ValueError(msg) from e
        except Exception as e:
            msg = f"Error loading documents: {e}"
            raise ValueError(msg) from e

        if len(docs) != 1:
            msg = "Expected a single document to be loaded."
            raise ValueError(msg)

        data = docs_to_data(docs)
        # Return the loaded documents
        self.status = data
        return Data(data={"text": data})
