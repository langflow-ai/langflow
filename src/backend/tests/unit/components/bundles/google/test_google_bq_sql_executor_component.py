"""Tests for BigQueryExecutorComponent."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.service_account import Credentials
from langflow.components.google.google_bq_sql_executor import BigQueryExecutorComponent
from pandas import DataFrame

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
                "client_x509_cert_url": (
                    "https://www.googleapis.com/robot/v1/metadata/x509/test@project.iam.gserviceaccount.com"
                ),
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
        mock_creds = MagicMock(spec=Credentials)
        mock_from_file.return_value = mock_creds

        # Create a mock row that can be converted to a dict
        mock_row = MagicMock()
        mock_row.items.return_value = [("column1", "value1")]
        mock_row.__iter__.return_value = iter([("column1", "value1")])
        mock_row.keys.return_value = ["column1"]
        mock_row.to_numpy.return_value = ["value1"]  # Changed from values to to_numpy
        mock_row.__getitem__.return_value = "value1"

        # Create mock result with the mock row
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([mock_row])

        # Create mock job with the mock result
        mock_job = MagicMock()
        mock_job.result.return_value = mock_result

        # Create mock client with the mock job
        mock_client = MagicMock()
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client

        # Instantiate component with defaults
        component = component_class(**default_kwargs)

        # Execute
        result = component.execute_sql()

        # Verify the result
        assert isinstance(result, DataFrame)
        assert len(result) == 1  # Check number of rows
        assert "column1" in result.columns  # Check column exists
        assert result.iloc[0]["column1"] == "value1"  # Check value

        # Verify the mocks were called correctly
        mock_from_file.assert_called_once_with(default_kwargs["service_account_json_file"])
        mock_client_cls.assert_called_once_with(credentials=mock_creds, project="test-project")
        mock_client.query.assert_called_once_with(default_kwargs["query"])

    @pytest.mark.parametrize("q", ["", "   \n\t  "])
    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_empty_query_raises(self, mock_client_cls, mock_from_file, component_class, service_account_file, q):
        """Empty or whitespace-only queries should raise a ValueError."""
        # Create a proper mock credentials object
        mock_creds = MagicMock(spec=Credentials)
        mock_from_file.return_value = mock_creds

        # Mock the BigQuery client
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Create component with empty/whitespace query
        component = component_class(
            service_account_json_file=service_account_file,
            query=q,
        )

        # Verify that execute_sql raises ValueError for empty/whitespace queries
        expected_error = "No valid SQL query found in input text."
        with pytest.raises(ValueError, match=expected_error):
            component.execute_sql()

        # Verify that the BigQuery client was not called
        mock_client.query.assert_not_called()

    def test_missing_service_account_file(self, component_class):
        """Non-existent service account file should raise a ValueError."""
        component = component_class(
            service_account_json_file="/no/such/file.json",
            query="SELECT 1",
        )
        expected_error = "Service account file not found"
        with pytest.raises(ValueError, match=expected_error):
            component.execute_sql()

    def test_invalid_service_account_json(self, component_class):
        """Invalid JSON in service account file should raise a ValueError."""
        with patch("pathlib.Path.open", mock_open(read_data="invalid json")):
            component = component_class(
                service_account_json_file="ignored.json",
                query="SELECT 1",
            )
            expected_error = "Invalid JSON string for service account credentials"
            with pytest.raises(ValueError, match=expected_error):
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
        """Complex row structures should be correctly serialized to DataFrame."""
        # Arrange mocks
        mock_creds = MagicMock(spec=Credentials)
        mock_from_file.return_value = mock_creds

        # Create mock rows with complex data
        mock_row1 = MagicMock()
        mock_row1.items.return_value = [("id", 1), ("name", "Test 1"), ("value", 10.5), ("active", True)]
        mock_row1.__iter__.return_value = iter([("id", 1), ("name", "Test 1"), ("value", 10.5), ("active", True)])
        mock_row1.keys.return_value = ["id", "name", "value", "active"]
        mock_row1.to_numpy.return_value = [1, "Test 1", 10.5, True]  # Changed from values to to_numpy
        mock_row1.__getitem__.side_effect = lambda key: {"id": 1, "name": "Test 1", "value": 10.5, "active": True}[key]

        mock_row2 = MagicMock()
        mock_row2.items.return_value = [("id", 2), ("name", "Test 2"), ("value", 20.75), ("active", False)]
        mock_row2.__iter__.return_value = iter([("id", 2), ("name", "Test 2"), ("value", 20.75), ("active", False)])
        mock_row2.keys.return_value = ["id", "name", "value", "active"]
        mock_row2.to_numpy.return_value = [2, "Test 2", 20.75, False]  # Changed from values to to_numpy
        mock_row2.__getitem__.side_effect = lambda key: {"id": 2, "name": "Test 2", "value": 20.75, "active": False}[
            key
        ]

        # Create mock result with the mock rows
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([mock_row1, mock_row2])

        # Create mock job with the mock result
        mock_job = MagicMock()
        mock_job.result.return_value = mock_result

        # Create mock client with the mock job
        mock_client = MagicMock()
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client

        # Instantiate component with defaults
        component = component_class(**default_kwargs)

        # Execute
        result = component.execute_sql()

        # Verify the result
        assert isinstance(result, DataFrame)
        assert len(result) == 2  # Check number of rows
        assert list(result.columns) == ["id", "name", "value", "active"]  # Check columns

        # Convert DataFrame to dictionary for easier comparison
        result_dict = result.to_dict(orient="records")

        # Verify first row
        assert result_dict[0]["id"] == 1
        assert result_dict[0]["name"] == "Test 1"
        assert result_dict[0]["value"] == 10.5
        assert result_dict[0]["active"] is True

        # Verify second row
        assert result_dict[1]["id"] == 2
        assert result_dict[1]["name"] == "Test 2"
        assert result_dict[1]["value"] == 20.75
        assert result_dict[1]["active"] is False

        # Verify the mocks were called correctly
        mock_from_file.assert_called_once_with(default_kwargs["service_account_json_file"])
        mock_client_cls.assert_called_once_with(credentials=mock_creds, project="test-project")
        mock_client.query.assert_called_once_with(default_kwargs["query"])

    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_query_with_sql_code_block(self, mock_client_cls, mock_from_file, component_class, default_kwargs):
        """Test that queries with SQL code blocks are properly handled."""
        mock_from_file.return_value = MagicMock()
        fake_client = MagicMock()
        mock_client_cls.return_value = fake_client

        query_with_code_block = "```sql\nSELECT * FROM table\n```"
        component = component_class(**{**default_kwargs, "query": query_with_code_block, "clean_query": True})

        result = component.execute_sql()

        # Verify the query was properly cleaned (code block markers removed)
        fake_client.query.assert_called_once_with("SELECT * FROM table")
        assert isinstance(result, DataFrame)

    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_query_with_whitespace(self, mock_client_cls, mock_from_file, component_class, default_kwargs):
        """Test that queries with extra whitespace are properly handled."""
        # Arrange mocks
        mock_creds = MagicMock(spec=Credentials)
        mock_from_file.return_value = mock_creds

        # Create a mock row that can be converted to a dict
        mock_row = MagicMock()
        mock_row.items.return_value = [("column1", "value1")]
        mock_row.__iter__.return_value = iter([("column1", "value1")])
        mock_row.keys.return_value = ["column1"]
        mock_row.to_numpy.return_value = ["value1"]  # Changed from values to to_numpy
        mock_row.__getitem__.return_value = "value1"

        # Create mock result with the mock row
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([mock_row])

        # Create mock job with the mock result
        mock_job = MagicMock()
        mock_job.result.return_value = mock_result

        # Create mock client with the mock job
        mock_client = MagicMock()
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client

        query_with_whitespace = "  SELECT * FROM table  "
        component = component_class(**{**default_kwargs, "query": query_with_whitespace, "clean_query": True})

        result = component.execute_sql()

        # Verify the query was properly stripped
        mock_client.query.assert_called_once_with("SELECT * FROM table")
        assert isinstance(result, DataFrame)
        assert len(result) == 1  # Check number of rows
        assert "column1" in result.columns  # Check column exists
        assert result.iloc[0]["column1"] == "value1"  # Check value

    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_query_with_special_characters(self, mock_client_cls, mock_from_file, component_class, default_kwargs):
        """Test that queries with special characters are properly handled."""
        # Arrange mocks
        mock_creds = MagicMock(spec=Credentials)
        mock_from_file.return_value = mock_creds

        # Create a mock row that can be converted to a dict
        mock_row = MagicMock()
        mock_row.items.return_value = [("name", "test_value")]
        mock_row.__iter__.return_value = iter([("name", "test_value")])
        mock_row.keys.return_value = ["name"]
        mock_row.to_numpy.return_value = ["test_value"]  # Changed from values to to_numpy
        mock_row.__getitem__.return_value = "test_value"

        # Create mock result with the mock row
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([mock_row])

        # Create mock job with the mock result
        mock_job = MagicMock()
        mock_job.result.return_value = mock_result

        # Create mock client with the mock job
        mock_client = MagicMock()
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client

        query_with_special_chars = "SELECT * FROM project.dataset.table WHERE name LIKE '%test%'"
        component = component_class(**{**default_kwargs, "query": query_with_special_chars})

        result = component.execute_sql()

        # Verify the query with special characters was passed correctly
        mock_client.query.assert_called_once_with(query_with_special_chars)
        assert isinstance(result, DataFrame)
        assert len(result) == 1  # Check number of rows
        assert "name" in result.columns  # Check column exists
        assert result.iloc[0]["name"] == "test_value"  # Check value

    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_query_with_multiple_statements(self, mock_client_cls, mock_from_file, component_class, default_kwargs):
        """Test that queries with multiple statements are properly handled."""
        # Arrange mocks
        mock_creds = MagicMock(spec=Credentials)
        mock_from_file.return_value = mock_creds

        # Create a mock row that can be converted to a dict
        mock_row = MagicMock()
        mock_row.items.return_value = [("id", 1)]
        mock_row.__iter__.return_value = iter([("id", 1)])
        mock_row.keys.return_value = ["id"]
        mock_row.to_numpy.return_value = [1]  # Changed from values to to_numpy
        mock_row.__getitem__.return_value = 1

        # Create mock result with the mock row
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([mock_row])

        # Create mock job with the mock result
        mock_job = MagicMock()
        mock_job.result.return_value = mock_result

        # Create mock client with the mock job
        mock_client = MagicMock()
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client

        multi_statement_query = (
            "CREATE TABLE IF NOT EXISTS test_table (id INT64);\n"
            "INSERT INTO test_table VALUES (1);\n"
            "SELECT * FROM test_table;"
        )
        component = component_class(**{**default_kwargs, "query": multi_statement_query})

        result = component.execute_sql()

        # Verify the multi-statement query was passed correctly
        mock_client.query.assert_called_once_with(multi_statement_query)
        assert isinstance(result, DataFrame)
        assert len(result) == 1  # Check number of rows
        assert "id" in result.columns  # Check column exists
        assert result.iloc[0]["id"] == 1  # Check value

    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_query_with_parameters(self, mock_client_cls, mock_from_file, component_class, default_kwargs):
        """Test that queries with parameters are properly handled."""
        # Arrange mocks
        mock_creds = MagicMock(spec=Credentials)
        mock_from_file.return_value = mock_creds

        # Create a mock row that can be converted to a dict
        mock_row = MagicMock()
        mock_row.items.return_value = [("id", 1), ("name", "test_name")]
        mock_row.__iter__.return_value = iter([("id", 1), ("name", "test_name")])
        mock_row.keys.return_value = ["id", "name"]
        mock_row.to_numpy.return_value = [1, "test_name"]  # Changed from values to to_numpy
        mock_row.__getitem__.side_effect = lambda key: {"id": 1, "name": "test_name"}[key]

        # Create mock result with the mock row
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([mock_row])

        # Create mock job with the mock result
        mock_job = MagicMock()
        mock_job.result.return_value = mock_result

        # Create mock client with the mock job
        mock_client = MagicMock()
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client

        query_with_params = "SELECT * FROM table WHERE id = @id AND name = @name"
        component = component_class(**{**default_kwargs, "query": query_with_params})

        result = component.execute_sql()

        # Verify the parameterized query was passed correctly
        mock_client.query.assert_called_once_with(query_with_params)
        assert isinstance(result, DataFrame)
        assert len(result) == 1  # Check number of rows
        assert list(result.columns) == ["id", "name"]  # Check columns
        assert result.iloc[0]["id"] == 1  # Check id value
        assert result.iloc[0]["name"] == "test_name"  # Check name value

    def test_missing_project_id_in_credentials(self, component_class, tmp_path):
        """Test that missing project_id in credentials raises an error."""
        # Create a service account JSON without project_id
        invalid_credentials = {
            "type": "service_account",
            "private_key_id": "fake-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\nfake-key\n-----END PRIVATE KEY-----\n",
            "client_email": "test@project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test@project.iam.gserviceaccount.com",
        }

        # Write invalid credentials to a temp file
        f = tmp_path / "invalid_sa.json"
        f.write_text(json.dumps(invalid_credentials))

        component = component_class(
            service_account_json_file=str(f),
            query="SELECT 1",
        )

        with pytest.raises(ValueError, match="No project_id found in service account credentials file"):
            component.execute_sql()

    @patch.object(Credentials, "from_service_account_file")
    @patch("langflow.components.google.google_bq_sql_executor.bigquery.Client")
    def test_query_with_quotes(self, mock_client_cls, mock_from_file, component_class, default_kwargs):
        """Test that queries wrapped in quotes are properly handled."""
        # Arrange mocks
        mock_creds = MagicMock(spec=Credentials)
        mock_from_file.return_value = mock_creds

        # Create a mock row that can be converted to a dict
        mock_row = MagicMock()
        mock_row.items.return_value = [("column1", "value1")]
        mock_row.__iter__.return_value = iter([("column1", "value1")])
        mock_row.keys.return_value = ["column1"]
        mock_row.to_numpy.return_value = ["value1"]  # Changed from values to to_numpy
        mock_row.__getitem__.return_value = "value1"

        # Create mock result with the mock row
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([mock_row])

        # Create mock job with the mock result
        mock_job = MagicMock()
        mock_job.result.return_value = mock_result

        # Create mock client with the mock job
        mock_client = MagicMock()
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client

        # Test with double quotes
        query_with_double_quotes = '"SELECT * FROM table"'
        component = component_class(**{**default_kwargs, "query": query_with_double_quotes, "clean_query": True})
        result = component.execute_sql()
        mock_client.query.assert_called_once_with("SELECT * FROM table")
        assert isinstance(result, DataFrame)

        # Reset mocks for next test
        mock_client.reset_mock()

        # Test with single quotes
        query_with_single_quotes = "'SELECT * FROM table'"
        component = component_class(**{**default_kwargs, "query": query_with_single_quotes, "clean_query": True})
        result = component.execute_sql()
        mock_client.query.assert_called_once_with("SELECT * FROM table")
        assert isinstance(result, DataFrame)

        # Reset mocks for next test
        mock_client.reset_mock()

        # Test with SQL code block
        query_with_code_block = "```sql\nSELECT * FROM table\n```"
        component = component_class(**{**default_kwargs, "query": query_with_code_block, "clean_query": True})
        result = component.execute_sql()
        mock_client.query.assert_called_once_with("SELECT * FROM table")
        assert isinstance(result, DataFrame)

        # Reset mocks for next test
        mock_client.reset_mock()

        # Test with SQL code block and quotes
        query_with_code_block_and_quotes = '```sql\n"SELECT * FROM table"\n```'
        component = component_class(
            **{**default_kwargs, "query": query_with_code_block_and_quotes, "clean_query": True}
        )
        result = component.execute_sql()
        mock_client.query.assert_called_once_with("SELECT * FROM table")
        assert isinstance(result, DataFrame)

        # Reset mocks for next test
        mock_client.reset_mock()

        # Test with just backticks
        query_with_backticks = "`SELECT * FROM table`"
        component = component_class(**{**default_kwargs, "query": query_with_backticks, "clean_query": True})
        result = component.execute_sql()
        mock_client.query.assert_called_once_with("SELECT * FROM table")
        assert isinstance(result, DataFrame)

        # Reset mocks for next test
        mock_client.reset_mock()

        # Test with mixed markers
        query_with_mixed = '```sql\n`"SELECT * FROM table"`\n```'
        component = component_class(**{**default_kwargs, "query": query_with_mixed, "clean_query": True})
        result = component.execute_sql()
        mock_client.query.assert_called_once_with("SELECT * FROM table")
        assert isinstance(result, DataFrame)

        # Reset mocks for next test
        mock_client.reset_mock()

        # Test with backticks in the middle of the query
        query_with_middle_backticks = "SELECT * FROM project.dataset.table"
        component = component_class(**{**default_kwargs, "query": query_with_middle_backticks, "clean_query": True})
        result = component.execute_sql()
        mock_client.query.assert_called_once_with("SELECT * FROM project.dataset.table")
        assert isinstance(result, DataFrame)

        # Reset mocks for next test
        mock_client.reset_mock()

        # Test with multiple backticks in the query
        query_with_multiple_backticks = "SELECT * FROM project.dataset.table WHERE column = 'value'"
        component = component_class(**{**default_kwargs, "query": query_with_multiple_backticks, "clean_query": True})
        result = component.execute_sql()
        mock_client.query.assert_called_once_with("SELECT * FROM project.dataset.table WHERE column = 'value'")
        assert isinstance(result, DataFrame)
