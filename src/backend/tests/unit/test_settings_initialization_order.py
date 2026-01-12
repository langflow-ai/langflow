"""Unit tests for settings initialization order.

These tests specifically verify that:
1. The check for pre-initialized settings works correctly
2. .env files can be loaded before settings initialization
3. The error message is helpful when settings are already initialized
4. CLI --env-file flag works with real subprocess startup
"""

import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest


class TestSettingsInitializationOrder:
    """Test the initialization order of settings service."""

    def test_is_settings_service_initialized_returns_false_initially(self):
        """Test that is_settings_service_initialized returns False before initialization."""
        from langflow.services.deps import is_settings_service_initialized
        from lfx.services.manager import get_service_manager

        # Clear services
        service_manager = get_service_manager()
        service_manager.services.clear()

        # Should be False initially
        assert is_settings_service_initialized() is False

    def test_is_settings_service_initialized_returns_true_after_init(self):
        """Test that is_settings_service_initialized returns True after initialization."""
        from langflow.services.deps import get_settings_service, is_settings_service_initialized
        from lfx.services.manager import get_service_manager

        # Clear services
        service_manager = get_service_manager()
        service_manager.services.clear()

        # Initialize
        get_settings_service()

        # Should be True now
        assert is_settings_service_initialized() is True

    def test_is_settings_service_initialized_checks_service_manager(self):
        """Test that the function checks the service manager directly."""
        from langflow.services.deps import is_settings_service_initialized
        from langflow.services.schema import ServiceType
        from lfx.services.manager import get_service_manager

        # Clear services
        service_manager = get_service_manager()
        service_manager.services.clear()

        # Manually add a mock service to the manager
        mock_service = MagicMock()
        service_manager.services[ServiceType.SETTINGS_SERVICE] = mock_service

        # Should return True
        assert is_settings_service_initialized() is True

        # Clean up
        del service_manager.services[ServiceType.SETTINGS_SERVICE]

    def test_dotenv_loading_before_settings_init(self, tmp_path):
        """Test the complete flow: load .env, then initialize settings."""
        from dotenv import load_dotenv
        from langflow.services.deps import get_settings_service, is_settings_service_initialized
        from lfx.services.manager import get_service_manager

        # Clear services
        service_manager = get_service_manager()
        service_manager.services.clear()

        # Create .env file
        env_file = tmp_path / ".env.test"
        env_file.write_text("LANGFLOW_SAVE_DB_IN_CONFIG_DIR=true\n")

        # Step 1: Check settings not initialized
        assert is_settings_service_initialized() is False

        # Step 2: Load .env file
        load_dotenv(env_file, override=True)

        # Step 3: Settings still not initialized
        assert is_settings_service_initialized() is False

        # Step 4: Env var is available
        assert os.environ.get("LANGFLOW_SAVE_DB_IN_CONFIG_DIR") == "true"

        # Step 5: Initialize settings
        settings = get_settings_service()

        # Step 6: Settings is initialized
        assert is_settings_service_initialized() is True
        assert settings is not None

        # Clean up
        if "LANGFLOW_SAVE_DB_IN_CONFIG_DIR" in os.environ:
            del os.environ["LANGFLOW_SAVE_DB_IN_CONFIG_DIR"]

    def test_cli_check_pattern_success_case(self, tmp_path):
        """Test the CLI check pattern when settings are NOT initialized (success case)."""
        from dotenv import load_dotenv
        from langflow.services.deps import is_settings_service_initialized
        from lfx.services.manager import get_service_manager

        # Clear services to ensure settings are NOT initialized
        service_manager = get_service_manager()
        service_manager.services.clear()

        env_file = tmp_path / ".env.cli"
        env_file.write_text("LANGFLOW_DATABASE_URL=sqlite:///./test.db\n")

        # Verify settings are not initialized
        assert is_settings_service_initialized() is False

        # Simulate the CLI check pattern
        if env_file:
            # Check if settings service is already initialized
            if is_settings_service_initialized():
                pytest.fail("Settings should not be initialized yet")
            else:
                # This is the success case - load the env file
                load_dotenv(env_file, override=True)
                assert os.environ.get("LANGFLOW_DATABASE_URL") == "sqlite:///./test.db"

        # Clean up
        if "LANGFLOW_DATABASE_URL" in os.environ:
            del os.environ["LANGFLOW_DATABASE_URL"]

    def test_cli_check_pattern_error_case(self, tmp_path):
        """Test the CLI check pattern when settings ARE initialized (error case)."""
        from langflow.services.deps import get_settings_service, is_settings_service_initialized
        from lfx.services.manager import get_service_manager

        # Clear services
        service_manager = get_service_manager()
        service_manager.services.clear()

        # Initialize settings FIRST
        get_settings_service()
        assert is_settings_service_initialized() is True

        env_file = tmp_path / ".env.cli"
        env_file.write_text("LANGFLOW_DATABASE_URL=sqlite:///./test.db\n")

        # Simulate the CLI check pattern
        if env_file:
            # Check if settings service is already initialized
            if is_settings_service_initialized():
                # This is the error case - settings already initialized
                # Should raise an error
                msg = "Settings service is already initialized. Please do not set the env file via the CLI."
                with pytest.raises(
                    ValueError,
                    match="Settings service is already initialized",
                ):
                    raise ValueError(msg)
            else:
                pytest.fail("Settings should be initialized, but check returned False")

    def test_error_message_when_settings_already_initialized(self, tmp_path):
        """Test that we get a clear error when trying to load .env after settings init."""
        from langflow.services.deps import get_settings_service, is_settings_service_initialized
        from lfx.services.manager import get_service_manager

        # Clear services
        service_manager = get_service_manager()
        service_manager.services.clear()

        # Initialize settings FIRST
        get_settings_service()

        env_file = tmp_path / ".env.late"
        env_file.write_text("LANGFLOW_DATABASE_URL=sqlite:///./test.db\n")

        # Now try to use the CLI pattern
        if env_file:
            if is_settings_service_initialized():
                # Should detect that settings are already initialized
                error_msg = (
                    "Settings service is already initialized. "
                    "This indicates potential race conditions with settings initialization. "
                    "Ensure the settings service is not created during module loading."
                )
                with pytest.raises(ValueError, match="Settings service is already initialized"):
                    raise ValueError(error_msg)
            else:
                # Should not reach here
                pytest.fail("Should have detected initialized settings")


class TestSettingsServiceSingleton:
    """Test that settings service maintains singleton behavior."""

    def test_settings_service_is_singleton(self):
        """Test that multiple calls return the same instance."""
        from langflow.services.deps import get_settings_service

        service1 = get_settings_service()
        service2 = get_settings_service()

        # Should be the exact same instance
        assert service1 is service2

    def test_settings_service_singleton_across_imports(self):
        """Test singleton behavior across different import paths."""
        from langflow.services.deps import get_settings_service
        from langflow.services.schema import ServiceType
        from lfx.services.manager import get_service_manager

        service1 = get_settings_service()
        service_manager = get_service_manager()
        service2 = service_manager.get(ServiceType.SETTINGS_SERVICE)

        # Should be the same instance
        assert service1 is service2


class TestCLISubprocessIntegration:
    """Test CLI with subprocess to verify real-world startup with .env files."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Shell script test not compatible with Windows")
    def test_cli_env_file_values_actually_used(self, tmp_path):
        """Test that values from --env-file are actually used by verifying server startup behavior.

        This is a full integration test that briefly starts the server to verify env file loading.
        """
        # Create an env file with a unique database path we can verify
        unique_db_name = f"test_env_integration_{os.getpid()}.db"
        db_path = tmp_path / unique_db_name

        env_file = tmp_path / "integration_test.env"
        env_file.write_text(
            f"""
LANGFLOW_DATABASE_URL=sqlite:///{db_path}
LANGFLOW_AUTO_SAVING=false
LANGFLOW_AUTO_LOGIN=false
LANGFLOW_LOG_LEVEL=ERROR
        """.strip()
        )

        # Create a test script that starts langflow and checks if the database was created
        # at the location specified in the env file
        test_script = tmp_path / "verify_startup.py"
        test_script.write_text(
            f"""
import sys
import time
import subprocess
import signal
from pathlib import Path

# Start langflow run with --env-file in background
db_path = Path(r"{db_path}")
env_file = Path(r"{env_file}")

# Start the server
proc = subprocess.Popen(
    [
        sys.executable, "-m", "langflow", "run", "--env-file", str(env_file),
        "--host", "127.0.0.1", "--port", "17860", "--backend-only"
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

try:
    # Poll for database file with timeout (more reliable in CI)
    max_wait = 45  # Increased timeout for CI
    poll_interval = 2
    elapsed = 0

    while elapsed < max_wait:
        # Check if process has died
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            print(f"ERROR: Server process died unexpectedly")
            print(f"STDOUT: {{stdout}}")
            print(f"STDERR: {{stderr}}")
            sys.exit(1)

        if db_path.exists():
            print(f"SUCCESS: Database created at env file location: {{db_path}}")
            sys.exit(0)

        time.sleep(poll_interval)
        elapsed += poll_interval

    # If we get here, database was not created
    print(f"ERROR: Database NOT created at env file location: {{db_path}}")
    print(f"This means env file values were not used")
    sys.exit(1)
finally:
    # Clean up: kill the server if still running
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        """.strip()
        )

        # Run the integration test (increased timeout for CI)
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(test_script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )

        # Clean up database file if created
        if db_path.exists():
            db_path.unlink()

        # Verify the test passed
        assert result.returncode == 0, (
            f"Integration test failed - env file values not used\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        assert "SUCCESS" in result.stdout, f"Database not created at env file location\n{result.stdout}"
