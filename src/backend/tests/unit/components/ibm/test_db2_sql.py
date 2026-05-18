"""Unit tests for DB2 SQL Component."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from lfx.components.ibm.db2_sql import DB2SQLComponent
from lfx.schema.data import Data


class TestDB2SQLComponent:
    """Test DB2 SQL Component."""

    @pytest.fixture
    def component(self):
        """Create a DB2SQLComponent instance with valid inputs."""
        comp = DB2SQLComponent()
        comp.database = "TESTDB"
        comp.hostname = "localhost"
        comp.port = 50000
        comp.username = "testuser"
        comp.password = str(50000)
        comp.sql_query = "SELECT * FROM users"
        comp.max_rows = 100
        comp.read_only_mode = True
        comp.query_timeout = 30
        return comp

    def test_component_metadata(self):
        """Test component metadata is correctly set."""
        comp = DB2SQLComponent()
        assert comp.display_name == "IBM Db2 SQL"
        assert comp.description == "Execute SQL queries on IBM Db2 database with security controls"
        assert comp.icon == "DB2"
        assert comp.name == "DB2SQL"

    def test_missing_ibm_db_package(self, component):
        """Test error when ibm_db package is not installed."""
        with (
            patch.dict("sys.modules", {"ibm_db_dbi": None}),
            pytest.raises(ImportError, match="Could not import required DB2 packages"),
        ):
            component.execute_query()

    def test_invalid_database_name(self, component):
        """Test validation of database name."""
        component.database = "invalid; DROP TABLE users;"
        with pytest.raises(ValueError, match="Invalid connection parameters"):
            component.execute_query()

    def test_invalid_hostname(self, component):
        """Test validation of hostname."""
        component.hostname = "localhost; DROP TABLE users;"
        with pytest.raises(ValueError, match="Invalid connection parameters"):
            component.execute_query()

    def test_invalid_port(self, component):
        """Test validation of port number."""
        component.port = 99999
        with pytest.raises(ValueError, match="Invalid connection parameters"):
            component.execute_query()

    def test_missing_credentials(self, component):
        """Test error when credentials are missing."""
        component.username = ""
        with pytest.raises(ValueError, match="Missing required credentials"):
            component.execute_query()

    def test_missing_sql_query(self, component):
        """Test error when SQL query is missing."""
        component.sql_query = None
        with pytest.raises(ValueError, match="SQL Query is required"):
            component.execute_query()

    def test_read_only_mode_blocks_insert(self, component):
        """Test that read-only mode blocks INSERT queries."""
        component.sql_query = "INSERT INTO users VALUES (1, 'test')"
        component.read_only_mode = True
        with pytest.raises(ValueError, match="Query validation failed"):
            component.execute_query()

    def test_read_only_mode_blocks_update(self, component):
        """Test that read-only mode blocks UPDATE queries."""
        component.sql_query = "UPDATE users SET name='test' WHERE id=1"
        component.read_only_mode = True
        with pytest.raises(ValueError, match="Query validation failed"):
            component.execute_query()

    def test_read_only_mode_blocks_delete(self, component):
        """Test that read-only mode blocks DELETE queries."""
        component.sql_query = "DELETE FROM users WHERE id=1"
        component.read_only_mode = True
        with pytest.raises(ValueError, match="Query validation failed"):
            component.execute_query()

    def test_sql_injection_blocked(self, component):
        """Test that SQL injection attempts are blocked."""
        component.sql_query = "SELECT * FROM users; DROP TABLE users; --"
        with pytest.raises(ValueError, match="Query validation failed"):
            component.execute_query()

    def test_invalid_max_rows(self, component):
        """Test validation of max_rows parameter."""
        component.max_rows = 0
        with pytest.raises(ValueError, match="max_rows must be between 1 and 10000"):
            component.execute_query()

        component.max_rows = 10001
        with pytest.raises(ValueError, match="max_rows must be between 1 and 10000"):
            component.execute_query()

    def test_invalid_query_timeout(self, component):
        """Test validation of query_timeout parameter."""
        component.query_timeout = 0
        with pytest.raises(ValueError, match="query_timeout must be between 1 and 300"):
            component.execute_query()

        component.query_timeout = 301
        with pytest.raises(ValueError, match="query_timeout must be between 1 and 300"):
            component.execute_query()

    # Note: Database connection tests require actual DB2 instance
    # These are better suited for integration testing

    def test_database_error_handling(self, component):
        """Test handling of database errors."""
        with patch("sys.modules", {"ibm_db_dbi": MagicMock()}):
            import sys

            mock_ibm_db_dbi = sys.modules["ibm_db_dbi"]
            mock_ibm_db_dbi.DatabaseError = Exception
            mock_ibm_db_dbi.connect.side_effect = Exception("SQL30081N Communication error")

            with pytest.raises(RuntimeError, match="Connection failed"):
                component.execute_query()

    def test_query_from_data_object(self, component):
        """Test extracting query from Data object."""
        data = Data(data={"text": "SELECT * FROM products"})
        component.sql_query = data

        # Mock the database connection
        with patch("lfx.components.ibm.db2_sql.ibm_db_dbi") as mock_ibm_db_dbi:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchmany.return_value = []
            mock_cursor.description = []
            mock_conn.cursor.return_value = mock_cursor
            mock_ibm_db_dbi.connect.return_value = mock_conn

            component.execute_query()

            # Verify cursor.execute was called with the extracted SQL
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0][0]
            assert "SELECT * FROM products" in call_args

    def test_query_from_message_object(self, component):
        """Test extracting query from Message-like object."""
        message = Mock()
        message.text = "SELECT * FROM products"
        component.sql_query = message

        # Mock the database connection
        with patch("lfx.components.ibm.db2_sql.ibm_db_dbi") as mock_ibm_db_dbi:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchmany.return_value = []
            mock_cursor.description = []
            mock_conn.cursor.return_value = mock_cursor
            mock_ibm_db_dbi.connect.return_value = mock_conn

            component.execute_query()

            # Verify cursor.execute was called with the extracted SQL
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0][0]
            assert "SELECT * FROM products" in call_args


# Made with Bob
