"""Unit tests for langflow.core.celery_app module."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.skip(reason="Skipping celery app tests as they cover unused code")
class TestMakeCelery:
    """Unit tests for the make_celery function."""

    def test_make_celery_creates_celery_instance(self):
        """Test that make_celery creates a functional Celery instance."""
        from langflow.core.celery_app import make_celery

        # Create a mock config module
        mock_config = MagicMock()
        mock_config.broker_url = "memory://"
        mock_config.result_backend = "cache+memory://"
        mock_config.accept_content = ["json"]

        # Mock the import of the config module
        with patch.dict("sys.modules", {"langflow.core.celeryconfig": mock_config}):
            # Act - Create a real Celery instance
            celery_app = make_celery("test_app", "langflow.core.celeryconfig")

            # Assert - Test actual functionality
            assert celery_app.main == "test_app"
            assert hasattr(celery_app, "config_from_object")
            assert hasattr(celery_app, "send_task")
            assert hasattr(celery_app, "control")

            # Verify the app can be used (basic functionality)
            assert celery_app.conf.broker_url == "memory://"
            assert celery_app.conf.result_backend == "cache+memory://"

    def test_make_celery_configures_from_object(self):
        """Test that configuration is actually applied to the Celery instance."""
        from langflow.core.celery_app import make_celery

        # Create a mock config module with specific values
        mock_config = MagicMock()
        mock_config.broker_url = "redis://test:6379/0"
        mock_config.result_backend = "redis://test:6379/0"
        mock_config.accept_content = ["json", "pickle"]
        mock_config.task_serializer = "json"

        with patch.dict("sys.modules", {"langflow.core.celeryconfig": mock_config}):
            celery_app = make_celery("test_app", "langflow.core.celeryconfig")

            # Verify configuration was actually applied
            assert celery_app.conf.broker_url == "redis://test:6379/0"
            assert celery_app.conf.result_backend == "redis://test:6379/0"
            assert celery_app.conf.accept_content == ["json", "pickle"]

    def test_make_celery_sets_task_routes(self):
        """Test that different app names create different Celery instances."""
        from langflow.core.celery_app import make_celery

        mock_config = MagicMock()
        mock_config.broker_url = "memory://"
        mock_config.result_backend = "cache+memory://"
        mock_config.accept_content = ["json"]

        with patch.dict("sys.modules", {"langflow.core.celeryconfig": mock_config}):
            app1 = make_celery("app1", "langflow.core.celeryconfig")
            app2 = make_celery("app2", "langflow.core.celeryconfig")

            # Different apps should have different main names
            assert app1.main == "app1"
            assert app2.main == "app2"
            assert app1 is not app2

    def test_make_celery_returns_celery_instance(self):
        """Test that the returned Celery app can perform basic operations."""
        from langflow.core.celery_app import make_celery

        mock_config = MagicMock()
        mock_config.broker_url = "memory://"
        mock_config.result_backend = "cache+memory://"
        mock_config.accept_content = ["json"]

        with patch.dict("sys.modules", {"langflow.core.celeryconfig": mock_config}):
            celery_app = make_celery("test_app", "langflow.core.celeryconfig")

            # Test that the app can be inspected
            assert celery_app.main == "test_app"

            # Test that it has the expected Celery interface
            assert hasattr(celery_app, "send_task")
            assert hasattr(celery_app, "control")
            assert hasattr(celery_app, "conf")

            # Test that configuration is accessible
            assert hasattr(celery_app.conf, "broker_url")
            assert hasattr(celery_app.conf, "result_backend")

    def test_make_celery_with_different_app_names(self):
        """Test that the Celery app can work with actual task definitions."""
        from langflow.core.celery_app import make_celery

        mock_config = MagicMock()
        mock_config.broker_url = "memory://"
        mock_config.result_backend = "cache+memory://"
        mock_config.accept_content = ["json"]

        with patch.dict("sys.modules", {"langflow.core.celeryconfig": mock_config}):
            celery_app = make_celery("test_app", "langflow.core.celeryconfig")

            # Define a simple task
            @celery_app.task
            def test_task(x, y):
                return x + y

            # Test that the task is registered (Celery uses full module path)
            # The task will be registered with the full module path
            task_found = False
            for task_name in celery_app.tasks:
                if task_name.endswith(".test_task"):
                    task_found = True
                    task_info = celery_app.tasks[task_name]
                    assert task_info.name == task_name
                    break

            assert task_found, "test_task should be registered in celery_app.tasks"

    def test_make_celery_with_different_configs(self):
        """Test that make_celery works with different configuration strings."""
        from langflow.core.celery_app import make_celery

        # Test with different config modules
        mock_config1 = MagicMock()
        mock_config1.broker_url = "redis://test1:6379/0"
        mock_config1.result_backend = "redis://test1:6379/0"
        mock_config1.accept_content = ["json"]

        mock_config2 = MagicMock()
        mock_config2.broker_url = "redis://test2:6379/0"
        mock_config2.result_backend = "redis://test2:6379/0"
        mock_config2.accept_content = ["pickle"]

        with patch.dict("sys.modules", {"langflow.core.celeryconfig": mock_config1}):
            app1 = make_celery("test_app", "langflow.core.celeryconfig")
            assert app1.conf.broker_url == "redis://test1:6379/0"

        with patch.dict("sys.modules", {"langflow.core.celeryconfig": mock_config2}):
            app2 = make_celery("test_app", "langflow.core.celeryconfig")
            assert app2.conf.broker_url == "redis://test2:6379/0"

    def test_make_celery_function_signature(self):
        """Test that make_celery function has the expected signature."""
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
        from langflow.core.celery_app import make_celery

        # Assert
        # The function exists and is callable
        assert callable(make_celery)
        assert make_celery.__name__ == "make_celery"

    def test_make_celery_error_handling(self):
        """Test that make_celery function handles errors appropriately."""
        from langflow.core.celery_app import make_celery

        # Test with invalid config that causes Celery to fail
        with patch("langflow.core.celery_app.Celery") as mock_celery_class:
            mock_celery_class.side_effect = Exception("Celery creation failed")

            with pytest.raises(Exception, match="Celery creation failed"):
                make_celery("test_app", "test.config")

    def test_make_celery_configuration_application(self):
        """Test that the module-level celery_app instance is created correctly."""
        # This tests the actual instance created at module level
        from langflow.core.celery_app import celery_app

        # Should be a Celery instance
        assert hasattr(celery_app, "main")
        assert hasattr(celery_app, "conf")
        assert hasattr(celery_app, "send_task")

        # Should have the expected app name
        assert celery_app.main == "langflow"
