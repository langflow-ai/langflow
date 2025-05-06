import json
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.service_account import Credentials
from langflow.components.google.google_bq_sql_executor import BigQueryExecutorComponent
from langflow.schema.message import Message
from tests.base import ComponentTestBaseWithoutClient


class TestBigQueryExecutorComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return BigQueryExecutorComponent

    @pytest.fixture
    def mock_credentials_json(self):
        """Return a valid service account JSON string."""
        return json.dumps(
            {
                "type": "service_account",
                "project_id": "test-project",
                "private_key_id": "fake-key-id",
                "private_key": "-----BEGIN PRIVATE KEY-----\nfake-key\n-----END PRIVATE KEY-----\n",
                "client_email": "test@project.iam.gserviceaccount.com",
                "client_id": "123456789",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test@project.iam.gserviceaccount.com",
            }
        )

    @pytest.fixture
    def service_account_file(self, tmp_path, mock_credentials_json):
        """Write service account JSON to a temp file and return its path."""
        f = tmp_path / "sa.json"
        f.write_text(mock_credentials_json)
        return str(f)

    @pytest.fixture
    def default_kwargs(self, service_account_file):
        """Return default kwargs for component instantiation."""
        return {
            "service_account_json_file": service_account_file,
            "project_id": "test-project",
            "query": "SELECT 1",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """No version-specific files for this component."""
        return []

    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_execute_sql_success(self, mock_client_cls, mock_from_file, component_class, default_kwargs):
        """Test successful SQL execution and component side-effects."""
        # Arrange mocks
        mock_creds = MagicMock()
        mock_from_file.return_value = mock_creds

        fake_client = MagicMock()
        mock_client_cls.return_value = fake_client

        fake_job = MagicMock()
        fake_job.result.return_value = [{"column1": "value1"}]
        fake_client.query.return_value = fake_job

        # Instantiate component with defaults
        component = component_class(**default_kwargs)

        # Execute
        result = component.execute_sql()

        # Assert credential loading and client instantiation
        mock_from_file.assert_called_once_with(default_kwargs["service_account_json_file"])
        mock_client_cls.assert_called_once_with(credentials=mock_creds, project=default_kwargs["project_id"])
        fake_client.query.assert_called_once_with(default_kwargs["query"])

        # Assert output
        assert isinstance(result, Message)
        assert '"column1": "value1"' in result.text
        assert component.status.startswith("[")
        parsed = json.loads(result.text)
        assert parsed[0]["column1"] == "value1"

    @pytest.mark.parametrize("q", ["", "   \n\t  "])
    def test_empty_query_raises(self, component_class, service_account_file, q):
        """Empty or whitespace-only queries should raise a ValueError."""
        component = component_class(
            service_account_json_file=service_account_file,
            project_id="p",
            query=q,
        )
        with pytest.raises(ValueError, match="No valid SQL query found"):
            component.execute_sql()

    def test_missing_service_account_file(self, component_class):
        """Non-existent service account file should raise a ValueError."""
        component = component_class(
            service_account_json_file="/no/such/file.json",
            project_id="p",
            query="SELECT 1",
        )
        with pytest.raises(ValueError, match="Error loading service account credentials"):
            component.execute_sql()

    @patch.object(Credentials, "from_service_account_file", side_effect=json.JSONDecodeError("Expecting value", "", 0))
    def test_invalid_service_account_json(self, mock_from_file, component_class):
        """Invalid JSON in service account file should raise a ValueError."""
        component = component_class(
            service_account_json_file="ignored.json",
            project_id="p",
            query="SELECT 1",
        )
        with pytest.raises(ValueError, match="Invalid JSON string for service account credentials."):
            component.execute_sql()

    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_execute_sql_invalid_query(self, mock_client_cls, mock_from_file, component_class, default_kwargs):
        """SQL execution errors should be wrapped in ValueError."""
        mock_from_file.return_value = MagicMock()
        fake_client = MagicMock()
        mock_client_cls.return_value = fake_client
        fake_client.query.side_effect = Exception("Invalid query syntax")

        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Error executing BigQuery SQL query: Invalid query syntax"):
            component.execute_sql()

    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_refresh_error_handling(self, mock_client_cls, mock_from_file, component_class, default_kwargs):
        """RefreshError should produce an authentication ValueError."""
        mock_from_file.return_value = MagicMock()
        fake_client = MagicMock()
        mock_client_cls.return_value = fake_client
        fake_client.query.side_effect = RefreshError("Token expired")

        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Authentication error: Unable to refresh authentication token."):
            component.execute_sql()

    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_complex_query_result(self, mock_client_cls, mock_from_file, component_class, default_kwargs):
        """Complex row structures should be correctly serialized to JSON."""
        mock_from_file.return_value = MagicMock()
        fake_client = MagicMock()
        mock_client_cls.return_value = fake_client

        complex_result = [
            {"id": 1, "name": "Test 1", "value": 10.5, "active": True},
            {"id": 2, "name": "Test 2", "value": 20.75, "active": False},
        ]
        fake_job = MagicMock()
        fake_job.result.return_value = complex_result
        fake_client.query.return_value = fake_job

        component = component_class(**default_kwargs)
        result = component.execute_sql()

        assert isinstance(result, Message)
        for item in complex_result:
            for key, value in item.items():
                assert str(value) in result.text
