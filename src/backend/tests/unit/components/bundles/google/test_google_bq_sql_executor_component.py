import json
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.service_account import Credentials
from langflow.components.google.google_bq_sql_executor import BigQueryExecutorComponent
from langflow.field_typing import Message


@pytest.fixture
def component():
    """Create a fresh component instance."""
    return BigQueryExecutorComponent()


@pytest.fixture
def mock_credentials_json():
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
def service_account_file(tmp_path, mock_credentials_json):
    """Write service account JSON to a temp file and return its path."""
    f = tmp_path / "sa.json"
    f.write_text(mock_credentials_json)
    return str(f)


@pytest.fixture
def valid_inputs(service_account_file):
    """Valid inputs for the component."""
    return {
        "service_account_json_file": service_account_file,
        "project_id": "test-project",
        "query": "SELECT 1",
    }


@patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
@patch.object(Credentials, "from_service_account_file")
def test_execute_sql_success(mock_from_file, mock_bq_client_cls, component, valid_inputs):
    """Test successful SQL execution and proper side-effects."""
    # Arrange mocks
    mock_creds = MagicMock()
    mock_from_file.return_value = mock_creds

    fake_client = MagicMock()
    mock_bq_client_cls.return_value = fake_client

    fake_job = MagicMock()
    fake_job.result.return_value = [{"column1": "value1"}]
    fake_client.query.return_value = fake_job

    # Set inputs
    component.service_account_json_file = valid_inputs["service_account_json_file"]
    component.project_id = valid_inputs["project_id"]
    component.query = valid_inputs["query"]

    # Act
    result = component.execute_sql()

    # Assert client creation and query invocation
    mock_from_file.assert_called_once_with(valid_inputs["service_account_json_file"])
    mock_bq_client_cls.assert_called_once_with(credentials=mock_creds, project=valid_inputs["project_id"])
    fake_client.query.assert_called_once_with("SELECT 1")

    # Assert output Message and component.status
    assert isinstance(result, Message)
    assert '"column1": "value1"' in result.text
    assert component.status.startswith("[")
    parsed = json.loads(result.text)
    assert parsed[0]["column1"] == "value1"


@pytest.mark.parametrize("q", ["", "   \n\t  "])
def test_empty_query_raises(component, service_account_file, q):
    """Test that empty or whitespace-only queries raise a ValueError."""
    component.service_account_json_file = service_account_file
    component.project_id = "p"
    component.query = q

    with pytest.raises(ValueError, match="No valid SQL query found"):
        component.execute_sql()


def test_missing_service_account_file(component):
    """Test handling when the service account file does not exist."""
    component.service_account_json_file = "/path/does/not/exist.json"
    component.project_id = "p"
    component.query = "SELECT 1"

    with pytest.raises(ValueError, match="Error loading service account credentials"):
        component.execute_sql()


@patch.object(Credentials, "from_service_account_file", side_effect=json.JSONDecodeError("Expecting value", "", 0))
def test_invalid_service_account_json(mock_from_file, component):
    """Test JSONDecodeError path."""
    component.service_account_json_file = "ignored.json"
    component.project_id = "p"
    component.query = "SELECT 1"

    with pytest.raises(ValueError, match="Invalid JSON string for service account credentials."):
        component.execute_sql()


@patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
@patch.object(Credentials, "from_service_account_file")
def test_execute_sql_invalid_query(mock_from_file, mock_bq_client_cls, component, valid_inputs):
    """Test handling when the SQL query execution fails."""
    mock_from_file.return_value = MagicMock()
    fake_client = MagicMock()
    mock_bq_client_cls.return_value = fake_client
    fake_client.query.side_effect = Exception("Invalid query syntax")

    component.service_account_json_file = valid_inputs["service_account_json_file"]
    component.project_id = valid_inputs["project_id"]
    component.query = valid_inputs["query"]

    with pytest.raises(ValueError, match="Error executing BigQuery SQL query: Invalid query syntax"):
        component.execute_sql()


@patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
@patch.object(Credentials, "from_service_account_file")
def test_refresh_error_handling(mock_from_file, mock_bq_client_cls, component, valid_inputs):
    """Test handling of RefreshError during authentication."""
    mock_from_file.return_value = MagicMock()
    fake_client = MagicMock()
    mock_bq_client_cls.return_value = fake_client
    fake_client.query.side_effect = RefreshError("Token expired")

    component.service_account_json_file = valid_inputs["service_account_json_file"]
    component.project_id = valid_inputs["project_id"]
    component.query = valid_inputs["query"]

    with pytest.raises(ValueError, match="Authentication error: Unable to refresh authentication token."):
        component.execute_sql()


@patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
@patch.object(Credentials, "from_service_account_file")
def test_complex_query_result(mock_from_file, mock_bq_client_cls, component, valid_inputs):
    """Test successful execution with complex query results."""
    mock_from_file.return_value = MagicMock()
    fake_client = MagicMock()
    mock_bq_client_cls.return_value = fake_client

    complex_result = [
        {"id": 1, "name": "Test 1", "value": 10.5, "active": True},
        {"id": 2, "name": "Test 2", "value": 20.75, "active": False},
    ]
    fake_job = MagicMock()
    fake_job.result.return_value = complex_result
    fake_client.query.return_value = fake_job

    component.service_account_json_file = valid_inputs["service_account_json_file"]
    component.project_id = valid_inputs["project_id"]
    component.query = "SELECT id, name, value, active FROM test_table"

    result = component.execute_sql()

    assert isinstance(result, Message)
    for item in complex_result:
        for key, value in item.items():
            assert str(value) in result.text
