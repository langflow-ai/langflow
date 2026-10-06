"""Keep the single Google Doc and credential contracts across the provider upgrade."""

import json
from unittest.mock import patch

import pytest
from google.auth.exceptions import RefreshError
from langchain_core.documents import Document
from langchain_google_community import GoogleDriveLoader
from lfx_google.components.google.google_drive import GoogleDriveComponent


def component():
    return GoogleDriveComponent().set(
        json_string=json.dumps({"refresh_token": "test", "client_id": "test", "client_secret": "test"}),
        document_id="existing-doc",
    )


def test_drive_loads_known_document_without_mime_discovery():
    observed = []

    def load_document(loader, document_id):
        credentials = loader._load_credentials()
        observed.append((document_id, credentials.refresh_token))
        return Document(page_content="Saved document", metadata={"source": "existing-doc"})

    with (
        patch.object(GoogleDriveLoader, "_load_document_from_id", load_document),
        patch("googleapiclient.discovery.build", side_effect=AssertionError("Unexpected MIME discovery request")),
    ):
        data = component().load_documents()
    assert observed == [("existing-doc", "test")]
    assert data.data["text"][0].text == "Saved document"
    assert data.data["text"][0].data["source"] == "existing-doc"


def test_drive_retains_refresh_error_message():
    with (
        patch.object(GoogleDriveLoader, "_load_document_from_id", side_effect=RefreshError("expired")),
        pytest.raises(ValueError, match="Authentication error: Unable to refresh authentication token"),
    ):
        component().load_documents()
