import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.interface.initialize.loading import (
    update_params_with_load_from_db_fields,
    update_table_params_with_load_from_db_fields,
)


@pytest.mark.asyncio
async def test_update_params_fallback_to_env_when_variable_not_found():
    """Test that when a variable is not found in database and fallback_to_env_vars is True.

    It falls back to environment variables.
    """
    # Set up environment variable
    os.environ["TEST_API_KEY"] = "test-secret-key-123"

    # Create mock custom component
    custom_component = MagicMock()
    # Change this error message to avoid triggering re-raise
    custom_component.get_variable = AsyncMock(side_effect=ValueError("Database connection failed"))

    # Set up params with a field that should load from db
    params = {"api_key": "TEST_API_KEY"}
    load_from_db_fields = ["api_key"]

    # Call the function with fallback enabled
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        result = await update_params_with_load_from_db_fields(
            custom_component, params, load_from_db_fields, fallback_to_env_vars=True
        )

    # Should have fallen back to environment variable
    assert result["api_key"] == "test-secret-key-123"

    # Clean up
    del os.environ["TEST_API_KEY"]


@pytest.mark.asyncio
async def test_update_params_raises_when_variable_not_found_and_no_fallback():
    """Test that when a variable is not found and fallback_to_env_vars is False.

    It raises the error.
    """
    # Create mock custom component
    custom_component = MagicMock()
    custom_component.get_variable = AsyncMock(side_effect=ValueError("TEST_API_KEY variable not found."))

    # Set up params
    params = {"api_key": "TEST_API_KEY"}
    load_from_db_fields = ["api_key"]

    # Call the function with fallback disabled
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        with pytest.raises(ValueError, match="TEST_API_KEY variable not found"):
            await update_params_with_load_from_db_fields(
                custom_component, params, load_from_db_fields, fallback_to_env_vars=False
            )


@pytest.mark.asyncio
async def test_update_params_uses_database_variable_when_found():
    """Test that when a variable is found in database, it uses that value.

    It doesn't check environment variables.
    """
    # Set up environment variable (should not be used)
    os.environ["TEST_API_KEY"] = "env-value"

    # Create mock custom component
    custom_component = MagicMock()
    custom_component.get_variable = AsyncMock(return_value="db-value")

    # Set up params
    params = {"api_key": "TEST_API_KEY"}
    load_from_db_fields = ["api_key"]

    # Call the function
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        result = await update_params_with_load_from_db_fields(
            custom_component, params, load_from_db_fields, fallback_to_env_vars=True
        )

    # Should use database value, not environment value
    assert result["api_key"] == "db-value"

    # Clean up
    del os.environ["TEST_API_KEY"]


@pytest.mark.asyncio
async def test_update_params_sets_none_when_no_env_var_and_fallback_enabled():
    """Test that when variable not found in db and env var doesn't exist.

    The field is set to None.
    """
    # Make sure env var doesn't exist
    if "NONEXISTENT_KEY" in os.environ:
        del os.environ["NONEXISTENT_KEY"]

    # Create mock custom component
    custom_component = MagicMock()
    # Change this error message to avoid triggering re-raise
    custom_component.get_variable = AsyncMock(side_effect=ValueError("Database connection failed"))

    # Set up params
    params = {"api_key": "NONEXISTENT_KEY"}
    load_from_db_fields = ["api_key"]

    # Call the function with fallback enabled
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        result = await update_params_with_load_from_db_fields(
            custom_component, params, load_from_db_fields, fallback_to_env_vars=True
        )

    # Should be set to None
    assert result["api_key"] is None


@pytest.mark.asyncio
async def test_update_params_raises_on_user_id_not_set():
    """Test that 'User id is not set' error is always raised regardless of fallback setting."""
    # Create mock custom component
    custom_component = MagicMock()
    custom_component.get_variable = AsyncMock(side_effect=ValueError("User id is not set"))

    # Set up params
    params = {"api_key": "SOME_KEY"}
    load_from_db_fields = ["api_key"]

    # Should raise with fallback enabled
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        with pytest.raises(ValueError, match="User id is not set"):
            await update_params_with_load_from_db_fields(
                custom_component, params, load_from_db_fields, fallback_to_env_vars=True
            )

    # Should also raise with fallback disabled
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        with pytest.raises(ValueError, match="User id is not set"):
            await update_params_with_load_from_db_fields(
                custom_component, params, load_from_db_fields, fallback_to_env_vars=False
            )


@pytest.mark.asyncio
async def test_update_params_skips_empty_fields():
    """Test that empty or None fields in params are skipped."""
    # Create mock custom component
    custom_component = MagicMock()
    custom_component.get_variable = AsyncMock(return_value="some-value")

    # Set up params with empty and None values
    params = {"api_key": "", "another_key": None, "valid_key": "VALID_KEY"}
    load_from_db_fields = ["api_key", "another_key", "valid_key"]

    # Call the function
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session = MagicMock()
        mock_session_scope.return_value.__aenter__.return_value = mock_session

        result = await update_params_with_load_from_db_fields(
            custom_component, params, load_from_db_fields, fallback_to_env_vars=True
        )

    # Only valid_key should have been processed
    assert result["api_key"] == ""
    assert result["another_key"] is None
    assert result["valid_key"] == "some-value"

    # get_variable should only be called once for valid_key
    # Use ANY to match any session object instead of the specific mock
    from unittest.mock import ANY

    custom_component.get_variable.assert_called_once_with(name="VALID_KEY", field="valid_key", session=ANY)


@pytest.mark.asyncio
async def test_update_params_handles_multiple_fields():
    """Test that multiple fields are processed correctly with mixed results."""
    # Set up environment variables
    os.environ["ENV_KEY"] = "env-value"

    # Create mock custom component
    custom_component = MagicMock()

    # Set up different responses for different fields
    async def mock_get_variable(name, **_kwargs):
        if name == "DB_KEY":
            return "db-value"
        # Use error messages that won't trigger the re-raise condition
        if name == "ENV_KEY":
            error_msg = "Database connection failed"  # This won't trigger re-raise
            raise ValueError(error_msg)
        error_msg = "Database unavailable"  # This won't trigger re-raise
        raise ValueError(error_msg)

    custom_component.get_variable = AsyncMock(side_effect=mock_get_variable)

    # Set up params
    params = {"field1": "DB_KEY", "field2": "ENV_KEY", "field3": "MISSING_KEY"}
    load_from_db_fields = ["field1", "field2", "field3"]

    # Call the function with proper mocking - NOTICE THE CORRECT PATCH PATH
    with (
        patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope,
        patch("lfx.services.deps.get_settings_service") as mock_get_settings,
    ):
        # Create a proper mock session that won't be detected as NoopSession
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session_scope.return_value = mock_session

        # Mock settings service to ensure it doesn't use noop database
        mock_settings_service = MagicMock()
        mock_settings_service.settings.use_noop_database = False
        mock_get_settings.return_value = mock_settings_service

        result = await update_params_with_load_from_db_fields(
            custom_component, params, load_from_db_fields, fallback_to_env_vars=True
        )

    # Check results
    assert result["field1"] == "db-value"  # From database
    assert result["field2"] == "env-value"  # From environment (fallback)
    assert result["field3"] is None  # Not found anywhere

    # Clean up
    del os.environ["ENV_KEY"]


# =====================================================================================
# TABLE LOAD_FROM_DB TESTS
# =====================================================================================


@pytest.mark.asyncio
async def test_update_table_params_with_load_from_db_fields_basic():
    """Test basic table load_from_db functionality."""
    # Create mock custom component
    custom_component = MagicMock()

    # Mock database values
    async def mock_get_variable(name, **_kwargs):
        mock_values = {
            "ADMIN_USER": "actual_admin_user",
            "ADMIN_EMAIL": "admin@company.com",
        }
        if name in mock_values:
            return mock_values[name]
        msg = f"{name} variable not found."
        raise ValueError(msg)

    custom_component.get_variable = AsyncMock(side_effect=mock_get_variable)

    # Set up table params
    params = {
        "table_data": [
            {"username": "ADMIN_USER", "email": "ADMIN_EMAIL", "role": "admin"},
            {"username": "static_user", "email": "static@example.com", "role": "user"},
        ],
        "table_data_load_from_db_columns": ["username", "email"],
    }

    # Call the function
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        result = await update_table_params_with_load_from_db_fields(
            custom_component, params, "table_data", fallback_to_env_vars=False
        )

    # Check results
    table_data = result["table_data"]
    assert len(table_data) == 2

    # First row should have resolved values
    assert table_data[0]["username"] == "actual_admin_user"
    assert table_data[0]["email"] == "admin@company.com"
    assert table_data[0]["role"] == "admin"  # unchanged

    # Second row should have None for variables not found
    assert table_data[1]["username"] is None  # static_user not in mock DB
    assert table_data[1]["email"] is None  # static@example.com not in mock DB
    assert table_data[1]["role"] == "user"  # unchanged

    # Metadata should be removed
    assert "table_data_load_from_db_columns" not in result


@pytest.mark.asyncio
async def test_update_table_params_with_fallback_to_env():
    """Test table load_from_db with environment variable fallback."""
    # Set up environment variables
    os.environ["DB_USERNAME"] = "env_username"
    os.environ["DB_EMAIL"] = "env@example.com"

    # Create mock custom component
    custom_component = MagicMock()
    custom_component.get_variable = AsyncMock(side_effect=ValueError("variable not found."))

    # Set up table params
    params = {
        "table_data": [
            {"username": "DB_USERNAME", "email": "DB_EMAIL", "active": True},
        ],
        "table_data_load_from_db_columns": ["username", "email"],
    }

    # Call the function with fallback enabled
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        result = await update_table_params_with_load_from_db_fields(
            custom_component, params, "table_data", fallback_to_env_vars=True
        )

    # Check results - should use environment variables
    table_data = result["table_data"]
    assert table_data[0]["username"] == "env_username"
    assert table_data[0]["email"] == "env@example.com"
    assert table_data[0]["active"] is True  # unchanged

    # Clean up
    del os.environ["DB_USERNAME"]
    del os.environ["DB_EMAIL"]


@pytest.mark.asyncio
async def test_update_table_params_mixed_db_and_env():
    """Test table with some values from DB and some from environment."""
    # Set up environment variables
    os.environ["ENV_KEY"] = "from_environment"

    # Create mock custom component
    custom_component = MagicMock()

    async def mock_get_variable(name, **_kwargs):
        if name == "DB_KEY":
            return "from_database"
        msg = f"{name} variable not found."
        raise ValueError(msg)

    custom_component.get_variable = AsyncMock(side_effect=mock_get_variable)

    # Set up table params
    params = {
        "table_data": [
            {"field1": "DB_KEY", "field2": "ENV_KEY", "field3": "static_value"},
        ],
        "table_data_load_from_db_columns": ["field1", "field2"],
    }

    # Call the function with fallback enabled
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        result = await update_table_params_with_load_from_db_fields(
            custom_component, params, "table_data", fallback_to_env_vars=True
        )

    # Check results
    table_data = result["table_data"]
    assert table_data[0]["field1"] == "from_database"  # From DB
    assert table_data[0]["field2"] == "from_environment"  # From env fallback
    assert table_data[0]["field3"] == "static_value"  # Not in load_from_db_columns

    # Clean up
    del os.environ["ENV_KEY"]


@pytest.mark.asyncio
async def test_update_table_params_empty_table():
    """Test table load_from_db with empty table data."""
    custom_component = MagicMock()

    params = {
        "table_data": [],
        "table_data_load_from_db_columns": ["username", "email"],
    }

    result = await update_table_params_with_load_from_db_fields(
        custom_component, params, "table_data", fallback_to_env_vars=False
    )

    # Should return empty table and remove metadata
    assert result["table_data"] == []
    assert "table_data_load_from_db_columns" not in result


@pytest.mark.asyncio
async def test_update_table_params_no_load_from_db_columns():
    """Test table with no load_from_db columns."""
    custom_component = MagicMock()

    params = {
        "table_data": [{"field1": "value1", "field2": "value2"}],
        "table_data_load_from_db_columns": [],
    }

    result = await update_table_params_with_load_from_db_fields(
        custom_component, params, "table_data", fallback_to_env_vars=False
    )

    # Should return unchanged table and remove metadata
    assert result["table_data"] == [{"field1": "value1", "field2": "value2"}]
    assert "table_data_load_from_db_columns" not in result


@pytest.mark.asyncio
async def test_update_table_params_non_dict_rows():
    """Test table with non-dictionary rows (should be left unchanged)."""
    custom_component = MagicMock()
    custom_component.get_variable = AsyncMock(return_value="resolved_value")

    params = {
        "table_data": [
            {"username": "DB_USER"},  # dict row
            "string_row",  # non-dict row
            123,  # non-dict row
        ],
        "table_data_load_from_db_columns": ["username"],
    }

    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        result = await update_table_params_with_load_from_db_fields(
            custom_component, params, "table_data", fallback_to_env_vars=False
        )

    # Check results
    table_data = result["table_data"]
    assert len(table_data) == 3
    assert table_data[0]["username"] == "resolved_value"  # dict row processed
    assert table_data[1] == "string_row"  # non-dict row unchanged
    assert table_data[2] == 123  # non-dict row unchanged


@pytest.mark.asyncio
async def test_update_params_with_table_fields():
    """Test the main update_params function with table: prefix fields."""
    # Set up environment variable
    os.environ["TABLE_VAR"] = "table_env_value"

    # Create mock custom component
    custom_component = MagicMock()

    async def mock_get_variable(name, **_kwargs):
        if name == "REGULAR_VAR":
            return "regular_db_value"
        if name == "TABLE_VAR":
            return "table_db_value"
        msg = f"{name} variable not found."
        raise ValueError(msg)

    custom_component.get_variable = AsyncMock(side_effect=mock_get_variable)

    # Set up params with both regular and table fields
    params = {
        "regular_field": "REGULAR_VAR",
        "table_data": [
            {"username": "TABLE_VAR", "role": "admin"},
        ],
        "table_data_load_from_db_columns": ["username"],
    }

    load_from_db_fields = ["regular_field", "table:table_data"]

    # Call the main function (lfx version with table support)
    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        result = await update_params_with_load_from_db_fields(
            custom_component, params, load_from_db_fields, fallback_to_env_vars=False
        )

    # Check results
    assert result["regular_field"] == "regular_db_value"  # Regular field from DB

    table_data = result["table_data"]
    assert table_data[0]["username"] == "table_db_value"  # Table field from DB
    assert table_data[0]["role"] == "admin"  # Unchanged

    # Metadata should be removed
    assert "table_data_load_from_db_columns" not in result

    # Clean up
    del os.environ["TABLE_VAR"]


@pytest.mark.asyncio
async def test_update_table_params_handles_user_id_not_set_error():
    """Test that 'User id is not set' error is properly raised for table fields."""
    custom_component = MagicMock()
    custom_component.get_variable = AsyncMock(side_effect=ValueError("User id is not set"))

    params = {
        "table_data": [{"username": "SOME_VAR"}],
        "table_data_load_from_db_columns": ["username"],
    }

    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        with pytest.raises(ValueError, match="User id is not set"):
            await update_table_params_with_load_from_db_fields(
                custom_component, params, "table_data", fallback_to_env_vars=True
            )
