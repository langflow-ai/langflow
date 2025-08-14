"""Unit tests for langflow.core.celery_app module."""

from unittest.mock import MagicMock, Mock, patch

import pytest


class TestMakeCelery:
    """Unit tests for the make_celery function."""

    def test_make_celery_creates_celery_instance(self):
        """Test that make_celery creates a Celery instance with correct parameters."""
        # Arrange
        mock_celery_class = Mock()
        mock_celery_instance = Mock()
        mock_celery_class.return_value = mock_celery_instance

        # Act - Mock the entire celery module and import
        with (
            patch.dict("sys.modules", {"celery": MagicMock()}),
            patch("langflow.core.celery_app.Celery", mock_celery_class),
        ):
            # Now import and test the function
            from langflow.core.celery_app import make_celery

            result = make_celery("test_app", "test.config")

        # Assert
        mock_celery_class.assert_called_once_with("test_app")
        assert result == mock_celery_instance

    def test_make_celery_configures_from_object(self):
        """Test that make_celery calls config_from_object with the provided config."""
        # Arrange
        mock_celery_class = Mock()
        mock_celery_instance = Mock()
        mock_celery_class.return_value = mock_celery_instance

        # Act
        with (
            patch.dict("sys.modules", {"celery": MagicMock()}),
            patch("langflow.core.celery_app.Celery", mock_celery_class),
        ):
            from langflow.core.celery_app import make_celery

            make_celery("test_app", "test.config")

        # Assert
        mock_celery_instance.config_from_object.assert_called_once_with("test.config")

    def test_make_celery_sets_task_routes(self):
        """Test that make_celery sets the correct task routes configuration."""
        # Arrange
        mock_celery_class = Mock()
        mock_celery_instance = Mock()
        mock_celery_class.return_value = mock_celery_instance

        # Act
        with (
            patch.dict("sys.modules", {"celery": MagicMock()}),
            patch("langflow.core.celery_app.Celery", mock_celery_class),
        ):
            from langflow.core.celery_app import make_celery

            make_celery("test_app", "test.config")

        # Assert
        expected_routes = {"langflow.worker.tasks.*": {"queue": "langflow"}}
        assert mock_celery_instance.conf.task_routes == expected_routes

    def test_make_celery_returns_celery_instance(self):
        """Test that make_celery returns the configured Celery instance."""
        # Arrange
        mock_celery_class = Mock()
        mock_celery_instance = Mock()
        mock_celery_class.return_value = mock_celery_instance

        # Act
        with (
            patch.dict("sys.modules", {"celery": MagicMock()}),
            patch("langflow.core.celery_app.Celery", mock_celery_class),
        ):
            from langflow.core.celery_app import make_celery

            result = make_celery("test_app", "test.config")

        # Assert
        assert result is mock_celery_instance

    def test_make_celery_with_different_app_names(self):
        """Test that make_celery works with different application names."""
        # Arrange
        mock_celery_class = Mock()
        mock_celery_instance = Mock()
        mock_celery_class.return_value = mock_celery_instance

        # Act
        with (
            patch.dict("sys.modules", {"celery": MagicMock()}),
            patch("langflow.core.celery_app.Celery", mock_celery_class),
        ):
            from langflow.core.celery_app import make_celery

            result1 = make_celery("app1", "config1")
            result2 = make_celery("app2", "config2")

        # Assert
        assert mock_celery_class.call_count == 2
        mock_celery_class.assert_any_call("app1")
        mock_celery_class.assert_any_call("app2")
        assert result1 == mock_celery_instance
        assert result2 == mock_celery_instance

    def test_make_celery_with_different_configs(self):
        """Test that make_celery works with different configuration strings."""
        # Arrange
        mock_celery_class = Mock()
        mock_celery_instance = Mock()
        mock_celery_class.return_value = mock_celery_instance

        # Act
        with (
            patch.dict("sys.modules", {"celery": MagicMock()}),
            patch("langflow.core.celery_app.Celery", mock_celery_class),
        ):
            from langflow.core.celery_app import make_celery

            make_celery("test_app", "config1")
            make_celery("test_app", "config2")

        # Assert
        assert mock_celery_instance.config_from_object.call_count == 2
        mock_celery_instance.config_from_object.assert_any_call("config1")
        mock_celery_instance.config_from_object.assert_any_call("config2")

    def test_make_celery_function_signature(self):
        """Test that make_celery function has the expected signature."""
        # Arrange
        mock_celery_class = Mock()
        mock_celery_instance = Mock()
        mock_celery_class.return_value = mock_celery_instance

        # Act
        with (
            patch.dict("sys.modules", {"celery": MagicMock()}),
            patch("langflow.core.celery_app.Celery", mock_celery_class),
        ):
            import inspect

            from langflow.core.celery_app import make_celery

        # Assert
        sig = inspect.signature(make_celery)
        params = list(sig.parameters.keys())
        assert len(params) == 2
        assert "app_name" in params
        assert "config" in params

    def test_make_celery_docstring(self):
        """Test that make_celery function exists and is callable."""
        # Arrange
        mock_celery_class = Mock()
        mock_celery_instance = Mock()
        mock_celery_class.return_value = mock_celery_instance

        # Act
        with (
            patch.dict("sys.modules", {"celery": MagicMock()}),
            patch("langflow.core.celery_app.Celery", mock_celery_class),
        ):
            from langflow.core.celery_app import make_celery

        # Assert
        # The function exists and is callable
        assert callable(make_celery)
        assert make_celery.__name__ == "make_celery"

        # Note: The actual function doesn't have a docstring, so we test other attributes
        # This is a realistic test based on the actual implementation

    def test_make_celery_error_handling(self):
        """Test that make_celery function handles errors appropriately."""
        # Arrange
        mock_celery_class = Mock()
        mock_celery_class.side_effect = Exception("Celery creation failed")

        # Act & Assert
        with (
            patch.dict("sys.modules", {"celery": MagicMock()}),
            patch("langflow.core.celery_app.Celery", mock_celery_class),
        ):
            from langflow.core.celery_app import make_celery

            with pytest.raises(Exception, match="Celery creation failed"):
                make_celery("test_app", "test.config")

    def test_make_celery_configuration_application(self):
        """Test that make_celery function applies configuration correctly."""
        # Arrange
        mock_celery_class = Mock()
        mock_celery_instance = Mock()
        mock_celery_class.return_value = mock_celery_instance

        # Act
        with (
            patch.dict("sys.modules", {"celery": MagicMock()}),
            patch("langflow.core.celery_app.Celery", mock_celery_class),
        ):
            from langflow.core.celery_app import make_celery

            make_celery("test_app", "test.config")

        # Assert
        # Verify that config_from_object was called
        mock_celery_instance.config_from_object.assert_called_once_with("test.config")

        # Verify that task_routes was set
        expected_routes = {"langflow.worker.tasks.*": {"queue": "langflow"}}
        assert mock_celery_instance.conf.task_routes == expected_routes

        # Verify that the instance was returned
        assert mock_celery_instance is not None
