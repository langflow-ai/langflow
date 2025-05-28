import json

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from langflow.custom import Component
from langflow.inputs import DropdownInput, MessageTextInput
from langflow.io import SecretStrInput
from langflow.schema import Data
from langflow.template import Output


class GoogleDriveSearchComponent(Component):
    display_name = "Google Drive Search"
    description = "Searches Google Drive files using provided credentials and query parameters."
    icon = "Google"
    legacy: bool = True

    inputs = [
        SecretStrInput(
            name="token_string",
            display_name="Token String",
            info="JSON string containing OAuth 2.0 access token information for service account access",
            required=True,
        ),
        DropdownInput(
            name="query_item",
            display_name="Query Item",
            options=[
                "name",
                "fullText",
                "mimeType",
                "modifiedTime",
                "viewedByMeTime",
                "trashed",
                "starred",
                "parents",
                "owners",
                "writers",
                "readers",
                "sharedWithMe",
                "createdTime",
                "properties",
                "appProperties",
                "visibility",
                "shortcutDetails.targetId",
            ],
            info="The field to query.",
            required=True,
        ),
        DropdownInput(
            name="valid_operator",
            display_name="Valid Operator",
            options=["contains", "=", "!=", "<=", "<", ">", ">=", "in", "has"],
            info="Operator to use in the query.",
            required=True,
        ),
        MessageTextInput(
            name="search_term",
            display_name="Search Term",
            info="The value to search for in the specified query item.",
            required=True,
        ),
        MessageTextInput(
            name="query_string",
            display_name="Query String",
            info="The query string used for searching. You can edit this manually.",
            value="",  # This will be updated with the generated query string
        ),
    ]

    outputs = [
        Output(display_name="Document URLs", name="doc_urls", method="search_doc_urls"),
        Output(display_name="Document IDs", name="doc_ids", method="search_doc_ids"),
        Output(display_name="Document Titles", name="doc_titles", method="search_doc_titles"),
        Output(display_name="Data", name="Data", method="search_data"),
    ]

    def generate_query_string(self) -> str:
        query_item = self.query_item
        valid_operator = self.valid_operator
        search_term = self.search_term

        # Construct the query string
        query = f"{query_item} {valid_operator} '{search_term}'"

        # Update the editable query string input with the generated query
        self.query_string = query

        return query

    def on_inputs_changed(self) -> None:
        # Automatically regenerate the query string when inputs change
        self.generate_query_string()

    def generate_file_url(self, file_id: str, mime_type: str) -> str:
        """Generates the appropriate Google Drive URL for a file based on its MIME type."""
        return {
            "application/vnd.google-apps.document": f"https://docs.google.com/document/d/{file_id}/edit",
            "application/vnd.google-apps.spreadsheet": f"https://docs.google.com/spreadsheets/d/{file_id}/edit",
            "application/vnd.google-apps.presentation": f"https://docs.google.com/presentation/d/{file_id}/edit",
            "application/vnd.google-apps.drawing": f"https://docs.google.com/drawings/d/{file_id}/edit",
            "application/pdf": f"https://drive.google.com/file/d/{file_id}/view?usp=drivesdk",
        }.get(mime_type, f"https://drive.google.com/file/d/{file_id}/view?usp=drivesdk")

    def search_files(self) -> dict:
        # Load the token information from the JSON string
        token_info = json.loads(self.token_string)
        creds = Credentials.from_authorized_user_info(token_info)

        # Use the query string from the input (which might have been edited by the user)
        query = self.query_string or self.generate_query_string()

        # Initialize the Google Drive API service
        service = build("drive", "v3", credentials=creds)

        # Perform the search
        results = service.files().list(q=query, pageSize=5, fields="nextPageToken, files(id, name, mimeType)").execute()
        items = results.get("files", [])

        doc_urls = []
        doc_ids = []
        doc_titles_urls = []
        doc_titles = []

        if items:
            for item in items:
                # Directly use the file ID, title, and MIME type to generate the URL
                file_id = item["id"]
                file_title = item["name"]
                mime_type = item["mimeType"]
                file_url = self.generate_file_url(file_id, mime_type)

                # Store the URL, ID, and title+URL in their respective lists
                doc_urls.append(file_url)
                doc_ids.append(file_id)
                doc_titles.append(file_title)
                doc_titles_urls.append({"title": file_title, "url": file_url})

        return {"doc_urls": doc_urls, "doc_ids": doc_ids, "doc_titles_urls": doc_titles_urls, "doc_titles": doc_titles}

    def search_doc_ids(self) -> list[str]:
        return self.search_files()["doc_ids"]

    def search_doc_urls(self) -> list[str]:
        return self.search_files()["doc_urls"]

    def search_doc_titles(self) -> list[str]:
        return self.search_files()["doc_titles"]

    def search_data(self) -> Data:
        return Data(data={"text": self.search_files()["doc_titles_urls"]})
