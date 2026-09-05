import asyncio
import json
from json.decoder import JSONDecodeError

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from langchain_google_community import GoogleDriveLoader
from lfx.custom.custom_component.component import Component
from lfx.helpers.data import docs_to_data
from lfx.inputs.inputs import MessageTextInput
from lfx.io import SecretStrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output

from ._workspace_inputs import DRIVE_FILE_SCOPE, google_connection_input


class GoogleDriveComponent(Component):
    """Legacy single-document Drive loader, optionally backed by a connection (INT-10).

    The connection field resolves on ``drive.file``, so a managed connection can
    only load a document this app created or the user opened with it. Pasted
    token JSON keeps whatever reach its own grant had.
    """

    display_name = "Google Drive Loader"
    description = "Loads documents from Google Drive using a managed connection or provided credentials."
    icon = "Google"
    legacy: bool = True

    inputs = [
        google_connection_input(
            required_scopes=[DRIVE_FILE_SCOPE],
            required=False,
            info=(
                "Optional managed Google connection ('google/<name>'). On drive.file it reaches only "
                "files this app created or the user opened with it. Leave empty to paste token JSON."
            ),
        ),
        SecretStrInput(
            name="json_string",
            display_name="JSON String of the Service Account Token",
            info=(
                "JSON string containing OAuth 2.0 access token information. Leave empty when a "
                "managed connection is selected."
            ),
            required=False,
        ),
        MessageTextInput(
            name="document_id", display_name="Document ID", info="Single Google Drive document ID", required=True
        ),
    ]

    outputs = [
        Output(display_name="Loaded Documents", name="docs", method="load_documents"),
    ]

    async def load_documents(self) -> Data:
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

        document_ids = [self.document_id]
        if len(document_ids) != 1:
            msg = "Expected a single document ID"
            raise ValueError(msg)

        # TODO: Add validation to check if the document ID is valid

        creds = await self._resolve_credentials()

        # Initialize the custom loader with the provided credentials and document IDs
        loader = CustomGoogleDriveLoader(creds=creds, document_ids=document_ids)

        # Load the documents
        try:
            # GoogleDriveLoader.load() is blocking network I/O; keep it off the event loop.
            docs = await asyncio.to_thread(loader.load)
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

    async def _resolve_credentials(self) -> Credentials:
        """Build credentials from exactly one of the connection or the token JSON."""
        connection = (self.connection or "").strip() if self.connection else ""
        json_string = self.json_string or ""
        if connection and json_string.strip():
            msg = "Set either a managed Google connection or a token JSON string on the Google Drive Loader, not both."
            raise ValueError(msg)
        if connection:
            lease = self.resolve_connection("connection")
            return Credentials(token=await lease.get_token())
        if not json_string.strip():
            msg = "The Google Drive Loader needs either a managed Google connection or a token JSON string."
            raise ValueError(msg)
        try:
            token_info = json.loads(json_string)
        except JSONDecodeError as e:
            msg = "Invalid JSON string"
            raise ValueError(msg) from e
        return Credentials.from_authorized_user_info(token_info)
