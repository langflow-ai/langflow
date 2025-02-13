import pytest

from langflow.components.google import GoogleDriveComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGoogleDriveComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GoogleDriveComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "json_string": '{"type": "service_account", "project_id": "test-project", "private_key_id": "test-key-id", "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n", "client_email": "test-email@test.iam.gserviceaccount.com", "client_id": "test-client-id", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs", "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test-email%40test.iam.gserviceaccount.com"}',
            "document_id": "test-document-id",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_load_documents_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.load_documents()
        assert result is not None
        assert "text" in result.data
        assert isinstance(result.data["text"], str)

    def test_load_documents_invalid_json(self, component_class):
        invalid_kwargs = {
            "json_string": "invalid_json",
            "document_id": "test-document-id",
        }
        component = component_class(**invalid_kwargs)
        with pytest.raises(ValueError, match="Invalid JSON string"):
            component.load_documents()

    def test_load_documents_authentication_error(self, component_class):
        invalid_kwargs = {
            "json_string": '{"type": "service_account", "project_id": "test-project", "private_key_id": "test-key-id", "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n", "client_email": "test-email@test.iam.gserviceaccount.com", "client_id": "test-client-id", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs", "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test-email%40test.iam.gserviceaccount.com"}',
            "document_id": "invalid-document-id",
        }
        component = component_class(**invalid_kwargs)
        with pytest.raises(
            ValueError,
            match="Authentication error: Unable to refresh authentication token. Please try to reauthenticate.",
        ):
            component.load_documents()

    def test_load_documents_multiple_document_ids(self, component_class):
        invalid_kwargs = {
            "json_string": '{"type": "service_account", "project_id": "test-project", "private_key_id": "test-key-id", "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n", "client_email": "test-email@test.iam.gserviceaccount.com", "client_id": "test-client-id", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs", "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test-email%40test.iam.gserviceaccount.com"}',
            "document_id": "doc-id-1,doc-id-2",
        }
        component = component_class(**invalid_kwargs)
        with pytest.raises(ValueError, match="Expected a single document ID"):
            component.load_documents()
