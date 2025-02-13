import pytest

from langflow.components.google import GmailLoaderComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGmailLoaderComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GmailLoaderComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "json_string": '{"account": "", "client_id": "", "client_secret": "", "expiry": "", "refresh_token": "", "scopes": ["https://www.googleapis.com/auth/gmail.readonly"], "token": "", "token_uri": "https://oauth2.googleapis.com/token", "universe_domain": "googleapis.com"}',
            "label_ids": "INBOX,SENT,UNREAD,IMPORTANT",
            "max_results": "10",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_load_emails_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.load_emails()
        assert result is not None
        assert "data" in result.data
        assert isinstance(result.data["text"], list)

    def test_load_emails_invalid_json(self, component_class):
        component = component_class(json_string="invalid_json", label_ids="INBOX", max_results="10")
        with pytest.raises(ValueError, match="Invalid JSON string"):
            component.load_emails()

    def test_load_emails_authentication_error(self, component_class):
        invalid_json = '{"account": "", "client_id": "", "client_secret": "", "expiry": "", "refresh_token": "", "scopes": ["https://www.googleapis.com/auth/gmail.readonly"], "token": "", "token_uri": "https://oauth2.googleapis.com/token", "universe_domain": "googleapis.com"}'
        component = component_class(json_string=invalid_json, label_ids="INBOX", max_results="10")
        with pytest.raises(
            ValueError,
            match="Authentication error: Unable to refresh authentication token. Please try to reauthenticate.",
        ):
            component.load_emails()
