from unittest.mock import Mock, patch

import pytest
import sqlalchemy as sa
from langflow.utils.migration import column_exists, constraint_exists, foreign_key_exists, table_exists


class TestTableExists:
    """Test cases for table_exists function."""

    @patch("sqlalchemy.inspect")
    def test_table_exists_true(self, mock_inspect):
        """Test when table exists."""
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ["users", "posts", "comments"]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = table_exists("users", mock_conn)

        assert result is True
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_table_names.assert_called_once()

    @patch("sqlalchemy.inspect")
    def test_table_exists_false(self, mock_inspect):
        """Test when table does not exist."""
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ["users", "posts", "comments"]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = table_exists("nonexistent_table", mock_conn)

        assert result is False
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_table_names.assert_called_once()

    @patch("sqlalchemy.inspect")
    def test_table_exists_empty_database(self, mock_inspect):
        """Test when database has no tables."""
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = []
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = table_exists("any_table", mock_conn)

        assert result is False
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_table_names.assert_called_once()

    @patch("sqlalchemy.inspect")
    def test_table_exists_case_sensitive(self, mock_inspect):
        """Test case sensitivity of table name matching."""
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ["Users", "posts"]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        # Exact case match should work
        result = table_exists("Users", mock_conn)
        assert result is True

        # Different case should not match (depends on database implementation)
        result = table_exists("users", mock_conn)
        assert result is False

    @patch("sqlalchemy.inspect")
    def test_table_exists_with_engine(self, mock_inspect):
        """Test function works with both engine and connection objects."""
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ["test_table"]
        mock_inspect.return_value = mock_inspector

        mock_engine = Mock(spec=sa.engine.Engine)

        result = table_exists("test_table", mock_engine)

        assert result is True
        mock_inspect.assert_called_once_with(mock_engine)


class TestColumnExists:
    """Test cases for column_exists function."""

    @patch("sqlalchemy.inspect")
    def test_column_exists_true(self, mock_inspect):
        """Test when column exists in table."""
        mock_inspector = Mock()
        mock_inspector.get_columns.return_value = [
            {"name": "id", "type": "INTEGER"},
            {"name": "username", "type": "VARCHAR"},
            {"name": "email", "type": "VARCHAR"},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = column_exists("users", "username", mock_conn)

        assert result is True
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_columns.assert_called_once_with("users")

    @patch("sqlalchemy.inspect")
    def test_column_exists_false(self, mock_inspect):
        """Test when column does not exist in table."""
        mock_inspector = Mock()
        mock_inspector.get_columns.return_value = [
            {"name": "id", "type": "INTEGER"},
            {"name": "username", "type": "VARCHAR"},
            {"name": "email", "type": "VARCHAR"},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = column_exists("users", "nonexistent_column", mock_conn)

        assert result is False
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_columns.assert_called_once_with("users")

    @patch("sqlalchemy.inspect")
    def test_column_exists_empty_table(self, mock_inspect):
        """Test when table has no columns."""
        mock_inspector = Mock()
        mock_inspector.get_columns.return_value = []
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = column_exists("empty_table", "any_column", mock_conn)

        assert result is False
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_columns.assert_called_once_with("empty_table")

    @patch("sqlalchemy.inspect")
    def test_column_exists_case_sensitive(self, mock_inspect):
        """Test case sensitivity of column name matching."""
        mock_inspector = Mock()
        mock_inspector.get_columns.return_value = [
            {"name": "UserName", "type": "VARCHAR"},
            {"name": "email", "type": "VARCHAR"},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        # Exact case match should work
        result = column_exists("users", "UserName", mock_conn)
        assert result is True

        # Different case should not match
        result = column_exists("users", "username", mock_conn)
        assert result is False

    @patch("sqlalchemy.inspect")
    def test_column_exists_multiple_calls(self, mock_inspect):
        """Test multiple column existence checks on same table."""
        mock_inspector = Mock()
        mock_inspector.get_columns.return_value = [
            {"name": "id", "type": "INTEGER"},
            {"name": "name", "type": "VARCHAR"},
            {"name": "created_at", "type": "TIMESTAMP"},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        # Multiple checks should all work
        assert column_exists("posts", "id", mock_conn) is True
        assert column_exists("posts", "name", mock_conn) is True
        assert column_exists("posts", "created_at", mock_conn) is True
        assert column_exists("posts", "updated_at", mock_conn) is False

        # Inspector should be called for each check
        assert mock_inspect.call_count == 4
        assert mock_inspector.get_columns.call_count == 4


class TestForeignKeyExists:
    """Test cases for foreign_key_exists function."""

    @patch("sqlalchemy.inspect")
    def test_foreign_key_exists_true(self, mock_inspect):
        """Test when foreign key exists."""
        mock_inspector = Mock()
        mock_inspector.get_foreign_keys.return_value = [
            {"name": "fk_user_id", "constrained_columns": ["user_id"]},
            {"name": "fk_category_id", "constrained_columns": ["category_id"]},
            {"name": "fk_author_id", "constrained_columns": ["author_id"]},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = foreign_key_exists("posts", "fk_user_id", mock_conn)

        assert result is True
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_foreign_keys.assert_called_once_with("posts")

    @patch("sqlalchemy.inspect")
    def test_foreign_key_exists_false(self, mock_inspect):
        """Test when foreign key does not exist."""
        mock_inspector = Mock()
        mock_inspector.get_foreign_keys.return_value = [
            {"name": "fk_user_id", "constrained_columns": ["user_id"]},
            {"name": "fk_category_id", "constrained_columns": ["category_id"]},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = foreign_key_exists("posts", "fk_nonexistent", mock_conn)

        assert result is False
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_foreign_keys.assert_called_once_with("posts")

    @patch("sqlalchemy.inspect")
    def test_foreign_key_exists_no_foreign_keys(self, mock_inspect):
        """Test when table has no foreign keys."""
        mock_inspector = Mock()
        mock_inspector.get_foreign_keys.return_value = []
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = foreign_key_exists("simple_table", "any_fk", mock_conn)

        assert result is False
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_foreign_keys.assert_called_once_with("simple_table")

    @patch("sqlalchemy.inspect")
    def test_foreign_key_exists_none_names(self, mock_inspect):
        """Test when foreign keys have None names."""
        mock_inspector = Mock()
        mock_inspector.get_foreign_keys.return_value = [
            {"name": None, "constrained_columns": ["user_id"]},
            {"name": "fk_valid", "constrained_columns": ["category_id"]},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = foreign_key_exists("posts", "fk_valid", mock_conn)
        assert result is True

        # Should handle None names gracefully
        result = foreign_key_exists("posts", None, mock_conn)
        assert result is True  # None should match None

    @patch("sqlalchemy.inspect")
    def test_foreign_key_exists_case_sensitive(self, mock_inspect):
        """Test case sensitivity of foreign key name matching."""
        mock_inspector = Mock()
        mock_inspector.get_foreign_keys.return_value = [{"name": "FK_User_ID", "constrained_columns": ["user_id"]}]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        # Exact case match should work
        result = foreign_key_exists("posts", "FK_User_ID", mock_conn)
        assert result is True

        # Different case should not match
        result = foreign_key_exists("posts", "fk_user_id", mock_conn)
        assert result is False


class TestConstraintExists:
    """Test cases for constraint_exists function."""

    @patch("sqlalchemy.inspect")
    def test_constraint_exists_true(self, mock_inspect):
        """Test when constraint exists."""
        mock_inspector = Mock()
        mock_inspector.get_unique_constraints.return_value = [
            {"name": "uq_username", "column_names": ["username"]},
            {"name": "uq_email", "column_names": ["email"]},
            {"name": "uq_composite", "column_names": ["first_name", "last_name"]},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = constraint_exists("users", "uq_username", mock_conn)

        assert result is True
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_unique_constraints.assert_called_once_with("users")

    @patch("sqlalchemy.inspect")
    def test_constraint_exists_false(self, mock_inspect):
        """Test when constraint does not exist."""
        mock_inspector = Mock()
        mock_inspector.get_unique_constraints.return_value = [
            {"name": "uq_username", "column_names": ["username"]},
            {"name": "uq_email", "column_names": ["email"]},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = constraint_exists("users", "uq_nonexistent", mock_conn)

        assert result is False
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_unique_constraints.assert_called_once_with("users")

    @patch("sqlalchemy.inspect")
    def test_constraint_exists_no_constraints(self, mock_inspect):
        """Test when table has no unique constraints."""
        mock_inspector = Mock()
        mock_inspector.get_unique_constraints.return_value = []
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = constraint_exists("simple_table", "any_constraint", mock_conn)

        assert result is False
        mock_inspect.assert_called_once_with(mock_conn)
        mock_inspector.get_unique_constraints.assert_called_once_with("simple_table")

    @patch("sqlalchemy.inspect")
    def test_constraint_exists_none_names(self, mock_inspect):
        """Test when constraints have None names."""
        mock_inspector = Mock()
        mock_inspector.get_unique_constraints.return_value = [
            {"name": None, "column_names": ["id"]},
            {"name": "uq_valid", "column_names": ["username"]},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        result = constraint_exists("users", "uq_valid", mock_conn)
        assert result is True

        # Should handle None names gracefully
        result = constraint_exists("users", None, mock_conn)
        assert result is True  # None should match None

    @patch("sqlalchemy.inspect")
    def test_constraint_exists_case_sensitive(self, mock_inspect):
        """Test case sensitivity of constraint name matching."""
        mock_inspector = Mock()
        mock_inspector.get_unique_constraints.return_value = [{"name": "UQ_Username", "column_names": ["username"]}]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        # Exact case match should work
        result = constraint_exists("users", "UQ_Username", mock_conn)
        assert result is True

        # Different case should not match
        result = constraint_exists("users", "uq_username", mock_conn)
        assert result is False

    @patch("sqlalchemy.inspect")
    def test_constraint_exists_multiple_constraints(self, mock_inspect):
        """Test with multiple unique constraints."""
        mock_inspector = Mock()
        mock_inspector.get_unique_constraints.return_value = [
            {"name": "uq_single_column", "column_names": ["email"]},
            {"name": "uq_composite", "column_names": ["first_name", "last_name", "birth_date"]},
            {"name": "uq_another", "column_names": ["phone_number"]},
        ]
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        # All existing constraints should be found
        assert constraint_exists("users", "uq_single_column", mock_conn) is True
        assert constraint_exists("users", "uq_composite", mock_conn) is True
        assert constraint_exists("users", "uq_another", mock_conn) is True

        # Non-existing constraint should return False
        assert constraint_exists("users", "uq_missing", mock_conn) is False


class TestIntegrationScenarios:
    """Integration test scenarios for migration utilities."""

    @patch("sqlalchemy.inspect")
    def test_complete_migration_check_workflow(self, mock_inspect):
        """Test a complete migration check workflow."""
        mock_inspector = Mock()

        # Setup mock responses for different calls
        def get_table_names_side_effect():
            return ["users", "posts", "comments", "categories"]

        def get_columns_side_effect(table_name):
            columns_map = {
                "users": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "username", "type": "VARCHAR"},
                    {"name": "email", "type": "VARCHAR"},
                    {"name": "created_at", "type": "TIMESTAMP"},
                ],
                "posts": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "title", "type": "VARCHAR"},
                    {"name": "content", "type": "TEXT"},
                    {"name": "user_id", "type": "INTEGER"},
                ],
            }
            return columns_map.get(table_name, [])

        def get_foreign_keys_side_effect(table_name):
            fk_map = {"posts": [{"name": "fk_posts_user_id", "constrained_columns": ["user_id"]}]}
            return fk_map.get(table_name, [])

        def get_unique_constraints_side_effect(table_name):
            constraint_map = {
                "users": [
                    {"name": "uq_users_username", "column_names": ["username"]},
                    {"name": "uq_users_email", "column_names": ["email"]},
                ]
            }
            return constraint_map.get(table_name, [])

        mock_inspector.get_table_names.side_effect = get_table_names_side_effect
        mock_inspector.get_columns.side_effect = get_columns_side_effect
        mock_inspector.get_foreign_keys.side_effect = get_foreign_keys_side_effect
        mock_inspector.get_unique_constraints.side_effect = get_unique_constraints_side_effect
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        # Test complete migration check scenario
        # Check if tables exist
        assert table_exists("users", mock_conn) is True
        assert table_exists("posts", mock_conn) is True
        assert table_exists("nonexistent_table", mock_conn) is False

        # Check if required columns exist
        assert column_exists("users", "username", mock_conn) is True
        assert column_exists("users", "email", mock_conn) is True
        assert column_exists("posts", "user_id", mock_conn) is True
        assert column_exists("posts", "nonexistent_column", mock_conn) is False

        # Check if foreign keys exist
        assert foreign_key_exists("posts", "fk_posts_user_id", mock_conn) is True
        assert foreign_key_exists("posts", "nonexistent_fk", mock_conn) is False

        # Check if constraints exist
        assert constraint_exists("users", "uq_users_username", mock_conn) is True
        assert constraint_exists("users", "uq_users_email", mock_conn) is True
        assert constraint_exists("users", "nonexistent_constraint", mock_conn) is False

    @patch("sqlalchemy.inspect")
    def test_error_handling_in_inspection(self, mock_inspect):
        """Test error handling when SQLAlchemy inspection fails."""
        mock_inspector = Mock()
        mock_inspector.get_table_names.side_effect = Exception("Database connection error")
        mock_inspect.return_value = mock_inspector

        mock_conn = Mock()

        # Should propagate the exception
        with pytest.raises(Exception, match="Database connection error"):
            table_exists("any_table", mock_conn)

    @patch("sqlalchemy.inspect")
    def test_with_different_connection_types(self, mock_inspect):
        """Test functions work with different SQLAlchemy connection types."""
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ["test_table"]
        mock_inspect.return_value = mock_inspector

        # Test with mock engine
        mock_engine = Mock(spec=sa.engine.Engine)
        result = table_exists("test_table", mock_engine)
        assert result is True

        # Test with mock connection
        mock_connection = Mock(spec=sa.engine.Connection)
        result = table_exists("test_table", mock_connection)
        assert result is True

        # Verify inspect was called with the connection objects
        assert mock_inspect.call_count == 2
        mock_inspect.assert_any_call(mock_engine)
        mock_inspect.assert_any_call(mock_connection)
