import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.interface.initialize.loading import update_params_with_load_from_db_fields


@pytest.mark.asyncio
async def test_update_params_fallback_to_env_when_variable_not_found():
    """Test that when a variable is not found in database and fallback_to_env_vars is True.

    It falls back to environment variables.
    """
    # Set up environment variable
    os.environ["TEST_API_KEY"] = "test-secret-key-123"

    # Create mock custom component
    custom_component = MagicMock()
    custom_component.get_variable = AsyncMock(side_effect=ValueError("TEST_API_KEY variable not found."))

    # Set up params with a field that should load from db
    params = {"api_key": "TEST_API_KEY"}
    load_from_db_fields = ["api_key"]

    # Call the function with fallback enabled
    with patch("langflow.interface.initialize.loading.session_scope") as mock_session_scope:
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
    with patch("langflow.interface.initialize.loading.session_scope") as mock_session_scope:
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
    with patch("langflow.interface.initialize.loading.session_scope") as mock_session_scope:
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
    custom_component.get_variable = AsyncMock(side_effect=ValueError("NONEXISTENT_KEY variable not found."))

    # Set up params
    params = {"api_key": "NONEXISTENT_KEY"}
    load_from_db_fields = ["api_key"]

    # Call the function with fallback enabled
    with patch("langflow.interface.initialize.loading.session_scope") as mock_session_scope:
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
    with patch("langflow.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        with pytest.raises(ValueError, match="User id is not set"):
            await update_params_with_load_from_db_fields(
                custom_component, params, load_from_db_fields, fallback_to_env_vars=True
            )

    # Should also raise with fallback disabled
    with patch("langflow.interface.initialize.loading.session_scope") as mock_session_scope:
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
    with patch("langflow.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        result = await update_params_with_load_from_db_fields(
            custom_component, params, load_from_db_fields, fallback_to_env_vars=True
        )

    # Only valid_key should have been processed
    assert result["api_key"] == ""
    assert result["another_key"] is None
    assert result["valid_key"] == "some-value"

    # get_variable should only be called once for valid_key
    custom_component.get_variable.assert_called_once_with(
        name="VALID_KEY", field="valid_key", session=mock_session_scope.return_value.__aenter__.return_value
    )


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
        if name == "ENV_KEY":
            error_msg = "ENV_KEY variable not found."
            raise ValueError(error_msg)
        error_msg = f"{name} variable not found."
        raise ValueError(error_msg)

    custom_component.get_variable = AsyncMock(side_effect=mock_get_variable)

    # Set up params
    params = {"field1": "DB_KEY", "field2": "ENV_KEY", "field3": "MISSING_KEY"}
    load_from_db_fields = ["field1", "field2", "field3"]

    # Call the function
    with patch("langflow.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()

        result = await update_params_with_load_from_db_fields(
            custom_component, params, load_from_db_fields, fallback_to_env_vars=True
        )

    # Check results
    assert result["field1"] == "db-value"  # From database
    assert result["field2"] == "env-value"  # From environment
    assert result["field3"] is None  # Not found anywhere

    # Clean up
    del os.environ["ENV_KEY"]
