"""Example demonstrating how to properly use mock_database_session.

This file shows concrete examples of applying mock_database_session
to replace real database operations in unit tests.
"""

from unittest.mock import patch

import pytest

from tests.unit.shared_json import sample_database_records


class TestDatabaseMockingExamples:
    """Examples showing different ways to use mock_database_session."""

    def test_crud_operations(self, mock_database_session):
        """Test basic CRUD operations with mock database."""
        # Create - Test adding a record
        new_record = {"id": 99, "name": "New User", "email": "new@example.com"}
        mock_database_session.add(new_record)
        mock_database_session.commit()

        # Verify the add and commit were called
        mock_database_session.add.assert_called_once_with(new_record)
        mock_database_session.commit.assert_called_once()

        # Read - Test querying records
        mock_result = mock_database_session.exec.return_value
        mock_result.all.return_value = [new_record]

        records = mock_database_session.exec("SELECT * FROM users").all()
        assert len(records) == 1
        assert records[0]["name"] == "New User"

        # Update - Test updating a record
        mock_database_session.refresh(new_record)
        mock_database_session.commit()
        mock_database_session.refresh.assert_called_once_with(new_record)

        # Delete - Test deleting a record
        mock_database_session.delete(new_record)
        mock_database_session.commit()
        mock_database_session.delete.assert_called_once_with(new_record)

    def test_query_with_sample_data(self, mock_database_session, sample_database_records):
        """Test querying with shared sample data."""
        # Configure mock to return sample records
        mock_result = mock_database_session.exec.return_value
        mock_result.all.return_value = sample_database_records

        # Simulate component/service method that queries database
        def get_active_records(session):
            result = session.exec("SELECT * FROM records WHERE active = true")
            return result.all()

        # Test the function
        active_records = get_active_records(mock_database_session)

        # Verify results using shared sample data
        assert len(active_records) == 3
        assert active_records[0]["name"] == "Test Record 1"
        assert active_records[0]["active"] is True

        # Verify database was queried correctly
        mock_database_session.exec.assert_called_once_with("SELECT * FROM records WHERE active = true")

    def test_transaction_rollback(self, mock_database_session):
        """Test transaction rollback scenarios."""

        # Simulate a service method that should rollback on error
        def create_user_with_validation(session, user_data):
            try:
                if not user_data.get("email"):
                    msg = "Email is required"
                    raise ValueError(msg)
                session.add(user_data)
                session.commit()
            except Exception:
                return user_data
                session.rollback()
                raise

        # Test rollback on validation error
        invalid_user = {"name": "No Email User"}  # Missing email

        with pytest.raises(ValueError, match="Email is required"):
            create_user_with_validation(mock_database_session, invalid_user)

        # Verify rollback was called
        mock_database_session.rollback.assert_called_once()

    def test_database_connection_error(self, mock_database_session):
        """Test handling database connection errors."""
        # Configure mock to simulate connection failure
        mock_database_session.exec.side_effect = ConnectionError("Database unavailable")

        # Simulate a service method that handles connection errors
        def get_users_safely(session):
            try:
                result = session.exec("SELECT * FROM users")
                return result.all()
            except ConnectionError:
                return []  # Return empty list on connection error

        # Test that the service handles the error gracefully
        users = get_users_safely(mock_database_session)
        assert users == []

        # Verify the database was attempted
        mock_database_session.exec.assert_called_once_with("SELECT * FROM users")

    def test_pagination_queries(self, mock_database_session, sample_database_records):
        """Test pagination with mock database."""
        # Configure mock for paginated results
        page_1_records = sample_database_records[:2]  # First 2 records
        page_2_records = sample_database_records[2:]  # Remaining records

        # Mock different results for different calls
        mock_database_session.exec.side_effect = [
            type("MockResult", (), {"all": lambda: page_1_records})(),
            type("MockResult", (), {"all": lambda: page_2_records})(),
        ]

        # Simulate paginated queries
        def get_paginated_records(session, page, limit):
            offset = (page - 1) * limit
            # Using parameterized query pattern (mock doesn't need real SQL security)
            query = "SELECT * FROM records LIMIT ? OFFSET ?"
            return session.exec(query, limit, offset).all()

        # Test page 1
        page_1 = get_paginated_records(mock_database_session, page=1, limit=2)
        assert len(page_1) == 2
        assert page_1[0]["id"] == 1

        # Test page 2
        page_2 = get_paginated_records(mock_database_session, page=2, limit=2)
        assert len(page_2) == 1
        assert page_2[0]["id"] == 3

        # Verify correct queries were made
        actual_calls = mock_database_session.exec.call_args_list
        assert len(actual_calls) == 2

    def test_component_integration(self, mock_database_session):
        """Test how a component would integrate with mock database."""

        # Example component that uses database
        class UserManagerComponent:
            def __init__(self, database_session):
                self.db = database_session

            def get_user_count(self):
                result = self.db.exec("SELECT COUNT(*) as count FROM users")
                return result.first()["count"]

            def create_user(self, user_data):
                self.db.add(user_data)
                self.db.commit()
                return user_data

        # Configure mock for count query
        mock_count_result = mock_database_session.exec.return_value
        mock_count_result.first.return_value = {"count": 3}

        # Test the component
        component = UserManagerComponent(mock_database_session)

        # Test get_user_count
        count = component.get_user_count()
        assert count == 3
        mock_database_session.exec.assert_called_with("SELECT COUNT(*) as count FROM users")

        # Test create_user
        new_user = {"name": "Test User", "email": "test@example.com"}
        created_user = component.create_user(new_user)

        assert created_user == new_user
        mock_database_session.add.assert_called_once_with(new_user)
        mock_database_session.commit.assert_called_once()

    @patch("some_module.database_service")  # Example of patching a database service
    def test_service_layer_integration(self, mock_db_service, mock_database_session):
        """Test integration with service layer that uses database."""
        # Configure the patched service to use our mock database session
        mock_db_service.get_session.return_value = mock_database_session

        # Configure mock database responses
        mock_result = mock_database_session.exec.return_value
        mock_result.all.return_value = sample_database_records

        # Test service method (this would be your actual service code)
        def get_all_active_users():
            with mock_db_service.get_session() as session:
                result = session.exec("SELECT * FROM users WHERE active = true")
                return result.all()

        # Execute the test
        users = get_all_active_users()

        # Verify results
        assert len(users) == 3  # Based on sample_database_records

        # Verify service and database interactions
        mock_db_service.get_session.assert_called_once()
        mock_database_session.exec.assert_called_once_with("SELECT * FROM users WHERE active = true")


# Example of replacing existing database fixture with mock
class TestReplacingRealDatabaseFixtures:
    """Examples of converting real database tests to use mocks."""

    # BEFORE: Test using real database
    # @pytest.fixture
    # def real_database_session(self):
    #     engine = create_engine("sqlite:///test.db")
    #     session = Session(engine)
    #     yield session
    #     session.close()
    #
    # def test_with_real_database(self, real_database_session):
    #     user = User(name="Test")
    #     real_database_session.add(user)
    #     real_database_session.commit()
    #     # This hits the real database!

    # AFTER: Test using mock database
    def test_with_mock_database_replacement(self, mock_database_session):
        """Same test logic but with mock database (much faster!)."""
        user = {"name": "Test", "id": 1}
        mock_database_session.add(user)
        mock_database_session.commit()

        # Verify the operations were performed (without hitting real database)
        mock_database_session.add.assert_called_once_with(user)
        mock_database_session.commit.assert_called_once()

        # Test that queries return expected data
        mock_database_session.exec.return_value.first.return_value = user

        result = mock_database_session.exec("SELECT * FROM users WHERE id = 1").first()
        assert result["name"] == "Test"
