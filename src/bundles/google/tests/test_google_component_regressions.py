import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from google import genai
from google.auth.exceptions import RefreshError
from lfx.schema.dotdict import dotdict
from lfx_google.components.google import (
    GmailLoaderComponent,
    GoogleDriveSearchComponent,
    GoogleGenerativeAIComponent,
    GoogleOAuthToken,
)

TEST_API_KEY = "google-key"  # pragma: allowlist secret


def test_gmail_loader_rejects_non_numeric_max_results() -> None:
    component = GmailLoaderComponent()
    component.json_string = "{}"
    component.label_ids = "INBOX"
    component.max_results = "not-a-number"

    with pytest.raises(ValueError, match="Invalid max_results value: not-a-number"):
        component.load_emails()


def test_drive_search_rejects_invalid_token_json() -> None:
    component = GoogleDriveSearchComponent()
    component.token_string = "{invalid"  # noqa: S105

    with pytest.raises(ValueError, match="Invalid JSON string"):
        component.search_files()


def test_drive_search_reports_refresh_errors() -> None:
    component = GoogleDriveSearchComponent()
    component.token_string = "{}"  # noqa: S105
    component.query_string = "name contains 'report'"
    service = MagicMock()
    service.files.return_value.list.return_value.execute.side_effect = RefreshError("expired")

    with (
        patch(
            "lfx_google.components.google.google_drive_search.Credentials.from_authorized_user_info",
            return_value=MagicMock(),
        ),
        patch("lfx_google.components.google.google_drive_search.build", return_value=service),
        pytest.raises(ValueError, match="Authentication error: Unable to refresh authentication token"),
    ):
        component.search_files()


def test_google_model_discovery_uses_api_key_scoped_client() -> None:
    component = GoogleGenerativeAIComponent()
    component.api_key = TEST_API_KEY
    observed_api_keys: list[str] = []

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            observed_api_keys.append(api_key)
            self.models = SimpleNamespace(
                list=lambda: [
                    SimpleNamespace(name="models/gemini-a", supported_actions=["generateContent"]),
                    SimpleNamespace(name="models/embedding-a", supported_actions=["embedContent"]),
                ]
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

    with patch.object(genai, "Client", FakeClient):
        model_ids = component.get_models()

    assert observed_api_keys == ["google-key"]
    assert model_ids == ["gemini-a"]


def test_google_tool_filter_checks_each_candidate_without_skipping() -> None:
    component = GoogleGenerativeAIComponent()
    component.api_key = TEST_API_KEY

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == TEST_API_KEY
            self.models = SimpleNamespace(
                list=lambda: [
                    SimpleNamespace(name=f"models/gemini-{suffix}", supported_actions=["generateContent"])
                    for suffix in ("a", "b", "c")
                ]
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

    with (
        patch.object(genai, "Client", FakeClient),
        patch(
            "langchain_google_genai.chat_models.ChatGoogleGenerativeAI",
            side_effect=lambda **kwargs: SimpleNamespace(model=kwargs["model"]),
        ),
        patch.object(
            component,
            "supports_tool_calling",
            side_effect=lambda model: model.model in {"gemini-a", "gemini-c"},
        ),
    ):
        model_ids = component.get_models(tool_model_enabled=True)

    assert model_ids == ["gemini-c", "gemini-a"]


def test_google_model_config_handles_no_tool_capable_models() -> None:
    component = GoogleGenerativeAIComponent()
    component.api_key = TEST_API_KEY
    component.tool_model_enabled = True
    build_config = dotdict({"model_name": {"value": "gemini-old"}})

    with patch.object(component, "get_models", return_value=[]):
        updated = component.update_build_config(build_config, field_value=True, field_name="tool_model_enabled")

    assert updated["model_name"]["options"] == []
    assert "value" not in updated["model_name"]


@pytest.mark.parametrize(
    "scopes",
    [
        "https://www.googleapis.com/auth/drive.readonly",
        "mail.google.com/",
        "mail.google.com/, https://www.googleapis.com/auth/drive.readonly",
    ],
)
def test_oauth_scope_validation_accepts_separated_scopes(scopes: str) -> None:
    GoogleOAuthToken().validate_scopes(scopes)


def test_oauth_scope_validation_rejects_concatenated_scopes() -> None:
    scopes = "https://www.googleapis.com/auth/drive.readonlymail.google.com/"

    with pytest.raises(ValueError, match="Invalid scope format"):
        GoogleOAuthToken().validate_scopes(scopes)


def test_oauth_returns_credentials_without_shared_token_file() -> None:
    component = GoogleOAuthToken()
    component.scopes = "https://www.googleapis.com/auth/drive.readonly"
    component.oauth_credentials = "/tmp/google-client.json"
    credentials = MagicMock()
    credentials.to_json.return_value = json.dumps({"token": "test-token"})  # pragma: allowlist secret
    flow = MagicMock()
    flow.run_local_server.return_value = credentials

    with patch(
        "lfx_google.components.google.google_oauth_token.InstalledAppFlow.from_client_secrets_file",
        return_value=flow,
    ) as from_client_secrets_file:
        result = component.build_output()

    from_client_secrets_file.assert_called_once_with(
        "/tmp/google-client.json", ["https://www.googleapis.com/auth/drive.readonly"]
    )
    flow.run_local_server.assert_called_once_with(port=0, timeout_seconds=300)
    assert result.data == {"token": "test-token"}


def test_oauth_reports_callback_failure() -> None:
    component = GoogleOAuthToken()
    component.scopes = "https://www.googleapis.com/auth/drive.readonly"
    component.oauth_credentials = "/tmp/google-client.json"
    flow = MagicMock()
    flow.run_local_server.side_effect = TimeoutError("authorization timed out")

    with (
        patch(
            "lfx_google.components.google.google_oauth_token.InstalledAppFlow.from_client_secrets_file",
            return_value=flow,
        ),
        pytest.raises(ValueError, match="OAuth authorization failed: authorization timed out"),
    ):
        component.build_output()


def test_oauth_reports_invalid_client_credentials() -> None:
    component = GoogleOAuthToken()
    component.scopes = "https://www.googleapis.com/auth/drive.readonly"
    component.oauth_credentials = "/tmp/google-client.json"

    with (
        patch(
            "lfx_google.components.google.google_oauth_token.InstalledAppFlow.from_client_secrets_file",
            side_effect=ValueError("invalid client credentials"),
        ),
        pytest.raises(ValueError, match="OAuth authorization failed: invalid client credentials"),
    ):
        component.build_output()
