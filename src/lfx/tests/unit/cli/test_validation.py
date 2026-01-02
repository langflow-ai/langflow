"""Tests for CLI validation utilities."""

from unittest.mock import MagicMock, patch

from lfx.cli.validation import is_valid_env_var_name, validate_global_variables_for_env
from lfx.graph.graph.base import Graph
from lfx.graph.vertex.base import Vertex


class TestIsValidEnvVarName:
    """Test cases for is_valid_env_var_name function."""

    def test_valid_env_var_names(self):
        """Test that valid environment variable names are accepted."""
        valid_names = [
            "MY_VAR",
            "_PRIVATE_VAR",
            "VAR123",
            "LONG_VARIABLE_NAME_123",
            "a",
            "A",
            "_",
            "__double_underscore__",
        ]

        for name in valid_names:
            assert is_valid_env_var_name(name), f"'{name}' should be valid"

    def test_invalid_env_var_names(self):
        """Test that invalid environment variable names are rejected."""
        invalid_names = [
            "MY VAR",  # Contains space
            "MY-VAR",  # Contains hyphen
            "123VAR",  # Starts with number
            "MY.VAR",  # Contains dot
            "MY@VAR",  # Contains special character
            "MY$VAR",  # Contains dollar sign
            "MY%VAR",  # Contains percent
            "MY(VAR)",  # Contains parentheses
            "MY[VAR]",  # Contains brackets
            "MY{VAR}",  # Contains braces
            "",  # Empty string
            " ",  # Just space
            "MY\nVAR",  # Contains newline
            "MY\tVAR",  # Contains tab
            "Глобальная_переменная",  # Contains non-ASCII characters
        ]

        for name in invalid_names:
            assert not is_valid_env_var_name(name), f"'{name}' should be invalid"


class TestValidateGlobalVariablesForEnv:
    """Test cases for validate_global_variables_for_env function."""

    @patch("lfx.cli.validation.get_settings_service")
    def test_no_validation_when_database_available(self, mock_get_settings):
        """Test that no validation occurs when database is available."""
        # Mock settings to indicate database is available
        mock_settings_service = MagicMock()
        mock_settings_service.settings.use_noop_database = False
        mock_get_settings.return_value = mock_settings_service

        # Create a mock graph with vertices
        graph = MagicMock(spec=Graph)
        vertex = MagicMock(spec=Vertex)
        vertex.load_from_db_fields = ["api_key"]
        vertex.params = {"api_key": "MY VAR WITH SPACES"}
        graph.vertices = [vertex]

        # Should return no errors since database is available
        errors = validate_global_variables_for_env(graph)
        assert errors == []

    @patch("lfx.cli.validation.get_settings_service")
    def test_validation_when_noop_database(self, mock_get_settings):
        """Test that validation occurs when using noop database."""
        # Mock settings to indicate noop database
        mock_settings_service = MagicMock()
        mock_settings_service.settings.use_noop_database = True
        mock_get_settings.return_value = mock_settings_service

        # Create a mock graph with vertices
        graph = MagicMock(spec=Graph)

        # Vertex with invalid variable name
        vertex1 = MagicMock(spec=Vertex)
        vertex1.id = "vertex1"
        vertex1.display_name = "OpenAI Model"
        vertex1.load_from_db_fields = ["api_key"]
        vertex1.params = {"api_key": "MY API KEY"}  # Invalid: contains spaces

        # Vertex with valid variable name
        vertex2 = MagicMock(spec=Vertex)
        vertex2.id = "vertex2"
        vertex2.display_name = "Anthropic Model"
        vertex2.load_from_db_fields = ["api_key"]
        vertex2.params = {"api_key": "ANTHROPIC_API_KEY"}  # Valid

        graph.vertices = [vertex1, vertex2]

        # Should return errors for the invalid variable
        errors = validate_global_variables_for_env(graph)
        assert len(errors) == 1
        assert "OpenAI Model" in errors[0]
        assert "vertex1" in errors[0]
        assert "MY API KEY" in errors[0]
        assert "invalid characters" in errors[0]

    @patch("lfx.cli.validation.get_settings_service")
    def test_multiple_invalid_fields(self, mock_get_settings):
        """Test validation with multiple invalid fields in same vertex."""
        # Mock settings to indicate noop database
        mock_settings_service = MagicMock()
        mock_settings_service.settings.use_noop_database = True
        mock_get_settings.return_value = mock_settings_service

        # Create a mock graph with vertices
        graph = MagicMock(spec=Graph)

        vertex = MagicMock(spec=Vertex)
        vertex.id = "vertex1"
        vertex.display_name = "Database Connection"
        vertex.load_from_db_fields = ["username", "password", "host"]
        vertex.params = {
            "username": "DB USER",  # Invalid: contains space
            "password": "DB-PASSWORD",  # Invalid: contains hyphen
            "host": "DB_HOST",  # Valid
        }

        graph.vertices = [vertex]

        # Should return errors for both invalid variables
        errors = validate_global_variables_for_env(graph)
        assert len(errors) == 2

        # Check that both errors are present
        error_text = " ".join(errors)
        assert "DB USER" in error_text
        assert "DB-PASSWORD" in error_text
        assert "DB_HOST" not in error_text  # Valid variable should not be in errors

    @patch("lfx.cli.validation.get_settings_service")
    def test_empty_or_none_values_ignored(self, mock_get_settings):
        """Test that empty or None values are ignored."""
        # Mock settings to indicate noop database
        mock_settings_service = MagicMock()
        mock_settings_service.settings.use_noop_database = True
        mock_get_settings.return_value = mock_settings_service

        # Create a mock graph with vertices
        graph = MagicMock(spec=Graph)

        vertex = MagicMock(spec=Vertex)
        vertex.id = "vertex1"
        vertex.display_name = "Test Component"
        vertex.load_from_db_fields = ["field1", "field2", "field3"]
        vertex.params = {
            "field1": "",  # Empty string - should be ignored
            "field2": None,  # None - should be ignored
            "field3": "VALID_VAR",  # Valid
        }

        graph.vertices = [vertex]

        # Should return no errors
        errors = validate_global_variables_for_env(graph)
        assert errors == []

    @patch("lfx.cli.validation.get_settings_service")
    def test_vertex_without_load_from_db_fields(self, mock_get_settings):
        """Test vertices without load_from_db_fields attribute."""
        # Mock settings to indicate noop database
        mock_settings_service = MagicMock()
        mock_settings_service.settings.use_noop_database = True
        mock_get_settings.return_value = mock_settings_service

        # Create a mock graph with vertices
        graph = MagicMock(spec=Graph)

        vertex = MagicMock(spec=Vertex)
        vertex.id = "vertex1"
        vertex.display_name = "Test Component"
        # No load_from_db_fields attribute
        delattr(vertex, "load_from_db_fields")

        graph.vertices = [vertex]

        # Should handle gracefully with getattr default
        errors = validate_global_variables_for_env(graph)
        assert errors == []

    @patch("lfx.cli.validation.get_settings_service")
    def test_non_string_values_ignored(self, mock_get_settings):
        """Test that non-string values are ignored."""
        # Mock settings to indicate noop database
        mock_settings_service = MagicMock()
        mock_settings_service.settings.use_noop_database = True
        mock_get_settings.return_value = mock_settings_service

        # Create a mock graph with vertices
        graph = MagicMock(spec=Graph)

        vertex = MagicMock(spec=Vertex)
        vertex.id = "vertex1"
        vertex.display_name = "Test Component"
        vertex.load_from_db_fields = ["field1", "field2", "field3"]
        vertex.params = {
            "field1": 123,  # Integer - should be ignored
            "field2": ["list"],  # List - should be ignored
            "field3": {"dict": "value"},  # Dict - should be ignored
        }

        graph.vertices = [vertex]

        # Should return no errors
        errors = validate_global_variables_for_env(graph)
        assert errors == []

    @patch("lfx.cli.validation.get_settings_service")
    def test_check_variables_option_in_execute(self, mock_get_settings):
        """Test that check_variables option controls validation in execute command."""
        # This test verifies the check_variables option works correctly
        # when used with the execute command (--check-variables/--no-check-variables)

        # Mock settings to indicate noop database
        mock_settings_service = MagicMock()
        mock_settings_service.settings.use_noop_database = True
        mock_get_settings.return_value = mock_settings_service

        # Create a mock graph with invalid variable
        graph = MagicMock(spec=Graph)
        vertex = MagicMock(spec=Vertex)
        vertex.id = "vertex1"
        vertex.display_name = "Test Component"
        vertex.load_from_db_fields = ["api_key"]
        vertex.params = {"api_key": "INVALID VAR NAME"}  # Invalid: contains spaces
        graph.vertices = [vertex]

        # When check_variables=True (default), validation should find errors
        errors = validate_global_variables_for_env(graph)
        assert len(errors) == 1
        assert "INVALID VAR NAME" in errors[0]

    @patch("lfx.cli.validation.get_settings_service")
    def test_check_variables_option_in_serve(self, mock_get_settings):
        """Test that check_variables option controls validation in serve command."""
        # This test verifies the check_variables option works correctly
        # when used with the serve command (--check-variables/--no-check-variables)

        # Mock settings to indicate noop database
        mock_settings_service = MagicMock()
        mock_settings_service.settings.use_noop_database = True
        mock_get_settings.return_value = mock_settings_service

        # Create a mock graph with invalid variable
        graph = MagicMock(spec=Graph)
        vertex = MagicMock(spec=Vertex)
        vertex.id = "vertex1"
        vertex.display_name = "API Component"
        vertex.load_from_db_fields = ["token"]
        vertex.params = {"token": "MY-API-TOKEN"}  # Invalid: contains hyphen
        graph.vertices = [vertex]

        # Validation should find errors when check is enabled
        errors = validate_global_variables_for_env(graph)
        assert len(errors) == 1
        assert "MY-API-TOKEN" in errors[0]
        assert "invalid characters" in errors[0]
