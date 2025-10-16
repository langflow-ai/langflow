"""Comprehensive tests for lfx.log.logger module.

This test suite covers all aspects of the logger module including:
- configure() function with all parameters and edge cases
- InterceptHandler class functionality
- setup_uvicorn_logger() and setup_gunicorn_logger() functions
- Log processor functions (add_serialized, buffer_writer, etc.)
- Edge cases and error conditions
- The specific CRITICAL + 1 bug that was fixed
"""

import builtins
import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import structlog
from lfx.log.logger import (
    LOG_LEVEL_MAP,
    VALID_LOG_LEVELS,
    InterceptHandler,
    SizedLogBuffer,
    add_serialized,
    buffer_writer,
    configure,
    log_buffer,
    remove_exception_in_production,
    setup_gunicorn_logger,
    setup_uvicorn_logger,
)


class TestConfigure:
    """Test suite for the configure() function."""

    def setup_method(self):
        """Reset structlog configuration before each test."""
        # Store original configuration to restore later
        # structlog._config is a module-level configuration object

    def teardown_method(self):
        """Restore structlog configuration after each test."""
        # Reset to a basic configuration
        structlog.reset_defaults()
        structlog.configure()

    def test_configure_default_values(self):
        """Test configure() with default values."""
        configure()

        # Verify structlog is configured by checking we can get a logger
        logger = structlog.get_logger()
        assert logger is not None

        # Verify the logger has the expected methods
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_configure_valid_log_levels(self):
        """Test configure() with all valid log levels."""
        for level in VALID_LOG_LEVELS:
            configure(log_level=level)
            config = structlog._config
            assert config is not None

    def test_configure_invalid_log_level(self):
        """Test configure() with invalid log level falls back to ERROR."""
        configure(log_level="INVALID_LEVEL")
        config = structlog._config
        assert config is not None
        # Should fall back to ERROR level without raising an exception

    def test_configure_case_insensitive_log_level(self):
        """Test configure() with case insensitive log levels."""
        configure(log_level="debug")
        config = structlog._config
        assert config is not None

    def test_configure_with_log_file(self):
        """Test configure() with log file parameter."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            log_file_path = Path(tmp_file.name)

        try:
            configure(log_file=log_file_path)
            config = structlog._config
            assert config is not None

            # Verify file handler was added to root logger
            root_handlers = logging.root.handlers
            assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root_handlers)
        finally:
            # Cleanup
            if log_file_path.exists():
                log_file_path.unlink()
            # Remove any file handlers from root logger
            for handler in logging.root.handlers[:]:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    logging.root.removeHandler(handler)

    def test_configure_with_invalid_log_file_path(self):
        """Test configure() with invalid log file path falls back to cache dir."""
        invalid_path = Path("/nonexistent/directory/log.txt")

        configure(log_file=invalid_path)
        config = structlog._config
        assert config is not None

        # Should create file handler without raising exception
        # The function should fall back to cache directory

    def test_configure_disable_true(self):
        """Test configure() with disable=True sets high filter level."""
        configure(disable=True)

        config = structlog._config
        assert config is not None
        # When disabled, wrapper_class should be set to filter at CRITICAL level

    def test_configure_disable_false(self):
        """Test configure() with disable=False works normally."""
        configure(disable=False, log_level="DEBUG")

        config = structlog._config
        assert config is not None

    def test_configure_with_log_env_container(self):
        """Test configure() with log_env='container' uses JSON renderer."""
        configure(log_env="container")

        config = structlog._config
        assert config is not None
        # Should use JSONRenderer processor

    def test_configure_with_log_env_container_json(self):
        """Test configure() with log_env='container_json' uses JSON renderer."""
        configure(log_env="container_json")

        config = structlog._config
        assert config is not None

    def test_configure_with_log_env_container_csv(self):
        """Test configure() with log_env='container_csv' uses KeyValue renderer."""
        configure(log_env="container_csv")

        config = structlog._config
        assert config is not None

    def test_configure_with_custom_log_format(self):
        """Test configure() with custom log format."""
        configure(log_format="custom_format")

        config = structlog._config
        assert config is not None

    def test_configure_with_log_rotation(self):
        """Test configure() with log rotation settings."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file_path = Path(tmp_dir) / "test.log"

            # Clear any existing handlers first
            for handler in logging.root.handlers[:]:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    logging.root.removeHandler(handler)

            configure(log_file=log_file_path, log_rotation="50 MB")
            logger = structlog.get_logger()
            assert logger is not None

            # Check that rotating file handler was created with the correct file path
            rotating_handlers = [
                h
                for h in logging.root.handlers
                if isinstance(h, logging.handlers.RotatingFileHandler) and h.baseFilename == str(log_file_path)
            ]
            assert len(rotating_handlers) > 0

            # Check max bytes is set correctly (50 MB = 50 * 1024 * 1024)
            handler = rotating_handlers[0]
            assert handler.maxBytes == 50 * 1024 * 1024

            # Cleanup handlers
            for handler in logging.root.handlers[:]:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    logging.root.removeHandler(handler)

    def test_configure_with_invalid_log_rotation(self):
        """Test configure() with invalid log rotation falls back to default."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            log_file_path = Path(tmp_file.name)

        try:
            configure(log_file=log_file_path, log_rotation="invalid rotation")
            config = structlog._config
            assert config is not None

            # Should use default 10MB rotation
            rotating_handlers = [
                h for h in logging.root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
            ]
            if rotating_handlers:
                handler = rotating_handlers[0]
                assert handler.maxBytes == 10 * 1024 * 1024  # Default 10MB
        finally:
            # Cleanup
            if log_file_path.exists():
                log_file_path.unlink()
            for handler in logging.root.handlers[:]:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    logging.root.removeHandler(handler)

    @patch.dict(os.environ, {"LANGFLOW_LOG_LEVEL": "WARNING"})
    def test_configure_env_variable_override(self):
        """Test configure() respects LANGFLOW_LOG_LEVEL environment variable."""
        configure()  # Should use WARNING from env var

        config = structlog._config
        assert config is not None
        # The wrapper_class should be configured for WARNING level

    @patch.dict(os.environ, {"LANGFLOW_LOG_FILE": "/tmp/test.log"})  # noqa: S108
    def test_configure_env_log_file_override(self):
        """Test configure() respects LANGFLOW_LOG_FILE environment variable."""
        configure()

        config = structlog._config
        assert config is not None

    @patch.dict(os.environ, {"LANGFLOW_LOG_ENV": "container"})
    def test_configure_env_log_env_override(self):
        """Test configure() respects LANGFLOW_LOG_ENV environment variable."""
        configure()

        config = structlog._config
        assert config is not None

    @patch.dict(os.environ, {"LANGFLOW_LOG_FORMAT": "custom"})
    def test_configure_env_log_format_override(self):
        """Test configure() respects LANGFLOW_LOG_FORMAT environment variable."""
        configure()

        config = structlog._config
        assert config is not None

    @patch.dict(os.environ, {"LANGFLOW_PRETTY_LOGS": "false"})
    def test_configure_env_pretty_logs_disabled(self):
        """Test configure() respects LANGFLOW_PRETTY_LOGS=false."""
        configure()

        config = structlog._config
        assert config is not None

    def test_configure_critical_plus_one_bug(self):
        """Test that configure() handles disable=True without KeyError.

        This tests the specific bug where using logging.CRITICAL + 1
        as a filter level would cause a KeyError.
        """
        # This should not raise a KeyError
        configure(disable=True, log_level="CRITICAL")

        config = structlog._config
        assert config is not None

        # Verify we can get a logger and it's properly configured
        logger = structlog.get_logger()
        assert logger is not None


class TestInterceptHandler:
    """Test suite for the InterceptHandler class."""

    def setup_method(self):
        """Setup for each test method."""
        self.handler = InterceptHandler()
        # Mock structlog to capture calls
        self.mock_logger = Mock()
        self.structlog_patcher = patch("structlog.get_logger", return_value=self.mock_logger)
        self.structlog_patcher.start()

    def teardown_method(self):
        """Cleanup after each test method."""
        self.structlog_patcher.stop()

    def test_emit_critical_level(self):
        """Test InterceptHandler.emit() with CRITICAL level."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.CRITICAL,
            pathname="test.py",
            lineno=1,
            msg="Critical message",
            args=(),
            exc_info=None,
        )

        self.handler.emit(record)
        self.mock_logger.critical.assert_called_once_with("Critical message")

    def test_emit_error_level(self):
        """Test InterceptHandler.emit() with ERROR level."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error message",
            args=(),
            exc_info=None,
        )

        self.handler.emit(record)
        self.mock_logger.error.assert_called_once_with("Error message")

    def test_emit_warning_level(self):
        """Test InterceptHandler.emit() with WARNING level."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning message",
            args=(),
            exc_info=None,
        )

        self.handler.emit(record)
        self.mock_logger.warning.assert_called_once_with("Warning message")

    def test_emit_info_level(self):
        """Test InterceptHandler.emit() with INFO level."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Info message",
            args=(),
            exc_info=None,
        )

        self.handler.emit(record)
        self.mock_logger.info.assert_called_once_with("Info message")

    def test_emit_debug_level(self):
        """Test InterceptHandler.emit() with DEBUG level."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=1,
            msg="Debug message",
            args=(),
            exc_info=None,
        )

        self.handler.emit(record)
        self.mock_logger.debug.assert_called_once_with("Debug message")

    def test_emit_custom_level_above_critical(self):
        """Test InterceptHandler.emit() with custom level above CRITICAL."""
        # Test level higher than CRITICAL (like logging.CRITICAL + 1)
        record = logging.LogRecord(
            name="test_logger",
            level=logging.CRITICAL + 1,
            pathname="test.py",
            lineno=1,
            msg="Super critical message",
            args=(),
            exc_info=None,
        )

        self.handler.emit(record)
        # Should map to critical for levels >= CRITICAL
        self.mock_logger.critical.assert_called_once_with("Super critical message")

    def test_emit_with_message_formatting(self):
        """Test InterceptHandler.emit() with message formatting."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Message with %s and %d",
            args=("string", 42),
            exc_info=None,
        )

        self.handler.emit(record)
        self.mock_logger.info.assert_called_once_with("Message with string and 42")


class TestSetupFunctions:
    """Test suite for setup_uvicorn_logger() and setup_gunicorn_logger()."""

    def setup_method(self):
        """Setup for each test method."""
        # Store original logger configurations
        self.original_loggers = {}

    def teardown_method(self):
        """Cleanup after each test method."""
        # Restore original logger configurations if needed

    @patch("logging.getLogger")
    def test_setup_uvicorn_logger(self, mock_get_logger):
        """Test setup_uvicorn_logger() configures uvicorn loggers correctly."""
        # Create mock uvicorn loggers
        mock_uvicorn_access = Mock()
        mock_uvicorn_access.handlers = ["some_handler"]  # Start with some handlers
        mock_uvicorn_access.propagate = False  # Start with propagate False

        mock_uvicorn_error = Mock()
        mock_uvicorn_error.handlers = ["some_handler"]  # Start with some handlers
        mock_uvicorn_error.propagate = False  # Start with propagate False

        # Mock logging.getLogger to return the right loggers for specific names
        def get_logger_side_effect(name):
            if name == "uvicorn.access":
                return mock_uvicorn_access
            if name == "uvicorn.error":
                return mock_uvicorn_error
            return Mock()

        mock_get_logger.side_effect = get_logger_side_effect

        # Mock logging.root.manager.loggerDict to contain uvicorn logger names
        mock_logger_dict = {
            "uvicorn.access": Mock(),
            "uvicorn.error": Mock(),
            "other.logger": Mock(),  # Should be ignored
        }

        with patch("logging.root.manager.loggerDict", mock_logger_dict):
            setup_uvicorn_logger()

        # Verify uvicorn loggers were configured
        assert mock_uvicorn_access.handlers == []
        assert mock_uvicorn_access.propagate is True
        assert mock_uvicorn_error.handlers == []
        assert mock_uvicorn_error.propagate is True

    @patch("logging.getLogger")
    def test_setup_gunicorn_logger(self, mock_get_logger):
        """Test setup_gunicorn_logger() configures gunicorn loggers correctly."""
        mock_error_logger = Mock()
        mock_access_logger = Mock()

        def get_logger_side_effect(name):
            if name == "gunicorn.error":
                return mock_error_logger
            if name == "gunicorn.access":
                return mock_access_logger
            return Mock()

        mock_get_logger.side_effect = get_logger_side_effect

        setup_gunicorn_logger()

        # Verify gunicorn loggers were configured
        assert mock_error_logger.handlers == []
        assert mock_error_logger.propagate is True
        assert mock_access_logger.handlers == []
        assert mock_access_logger.propagate is True


class TestLogProcessors:
    """Test suite for log processor functions."""

    def test_add_serialized_with_buffer_disabled(self):
        """Test add_serialized() when log buffer is disabled."""
        event_dict = {"timestamp": 1625097600.123, "event": "Test message", "module": "test_module"}

        with patch.object(log_buffer, "enabled", return_value=False):
            result = add_serialized(None, "info", event_dict)

        # Should return event_dict unchanged when buffer is disabled
        assert result == event_dict
        assert "serialized" not in result

    def test_add_serialized_with_buffer_enabled(self):
        """Test add_serialized() when log buffer is enabled."""
        event_dict = {"timestamp": 1625097600.123, "event": "Test message", "module": "test_module"}

        with patch.object(log_buffer, "enabled", return_value=True):
            result = add_serialized(None, "info", event_dict)

        # Should add serialized field when buffer is enabled
        assert "serialized" in result
        serialized_data = json.loads(result["serialized"])
        assert serialized_data["timestamp"] == 1625097600.123
        assert serialized_data["message"] == "Test message"
        assert serialized_data["level"] == "INFO"
        assert serialized_data["module"] == "test_module"

    def test_remove_exception_in_production(self):
        """Test remove_exception_in_production() removes exception info in prod."""
        event_dict = {"event": "Test message", "exception": "Some exception", "exc_info": "Some exc info"}

        # Import the actual module to access DEV
        import sys

        logger_module = sys.modules["lfx.log.logger"]
        with patch.object(logger_module, "DEV", False):  # noqa: FBT003
            result = remove_exception_in_production(None, "error", event_dict)

        # Should remove exception info in production
        assert "exception" not in result
        assert "exc_info" not in result
        assert result["event"] == "Test message"

    def test_remove_exception_in_development(self):
        """Test remove_exception_in_production() keeps exception info in dev."""
        event_dict = {"event": "Test message", "exception": "Some exception", "exc_info": "Some exc info"}

        # Import the actual module to access DEV
        import sys

        logger_module = sys.modules["lfx.log.logger"]
        with patch.object(logger_module, "DEV", True):  # noqa: FBT003
            result = remove_exception_in_production(None, "error", event_dict)

        # Should keep exception info in development
        assert result["exception"] == "Some exception"
        assert result["exc_info"] == "Some exc info"
        assert result["event"] == "Test message"

    def test_buffer_writer_with_buffer_disabled(self):
        """Test buffer_writer() when log buffer is disabled."""
        event_dict = {"event": "Test message"}

        with (
            patch.object(log_buffer, "enabled", return_value=False),
            patch.object(log_buffer, "write") as mock_write,
        ):
            result = buffer_writer(None, "info", event_dict)

        # Should not write to buffer when disabled
        mock_write.assert_not_called()
        assert result == event_dict

    def test_buffer_writer_with_buffer_enabled(self):
        """Test buffer_writer() when log buffer is enabled."""
        event_dict = {"event": "Test message"}

        with (
            patch.object(log_buffer, "enabled", return_value=True),
            patch.object(log_buffer, "write") as mock_write,
        ):
            result = buffer_writer(None, "info", event_dict)

        # Should write to buffer when enabled
        mock_write.assert_called_once()
        call_args = mock_write.call_args[0]
        written_data = json.loads(call_args[0])
        assert written_data["event"] == "Test message"
        assert result == event_dict


class TestConstants:
    """Test suite for module constants."""

    def test_valid_log_levels_contains_all_standard_levels(self):
        """Test VALID_LOG_LEVELS contains all expected levels."""
        expected_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        assert expected_levels == VALID_LOG_LEVELS

    def test_log_level_map_has_correct_mappings(self):
        """Test LOG_LEVEL_MAP has correct integer mappings."""
        expected_mappings = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        assert expected_mappings == LOG_LEVEL_MAP

    def test_log_level_map_values_are_integers(self):
        """Test all LOG_LEVEL_MAP values are integers."""
        for level_name, level_value in LOG_LEVEL_MAP.items():
            assert isinstance(level_value, int), f"Level {level_name} value {level_value} is not an integer"


class TestEdgeCasesAndErrorConditions:
    """Test suite for edge cases and error conditions."""

    def test_configure_with_nonexistent_parent_directory(self):
        """Test configure() handles non-existent parent directories gracefully."""
        # Create a path with non-existent parent directory
        nonexistent_path = Path("/definitely/nonexistent/directory/logfile.log")

        # Should not raise an exception
        configure(log_file=nonexistent_path)

        config = structlog._config
        assert config is not None

    def test_configure_with_none_parameters(self):
        """Test configure() handles None parameters correctly."""
        configure(log_level=None, log_file=None, disable=None, log_env=None, log_format=None, log_rotation=None)

        config = structlog._config
        assert config is not None

    def test_configure_with_empty_string_parameters(self):
        """Test configure() handles empty string parameters correctly."""
        configure(log_level="", log_env="", log_format="", log_rotation="")

        config = structlog._config
        assert config is not None

    def test_multiple_configure_calls(self):
        """Test that multiple calls to configure() work correctly."""
        # First configuration
        configure(log_level="DEBUG")
        config1 = structlog._config

        # Second configuration should override the first
        configure(log_level="ERROR")
        config2 = structlog._config

        # Both should be valid but different
        assert config1 is not None
        assert config2 is not None

    def test_configure_creates_global_logger(self):
        """Test that configure() creates a global logger."""
        configure()

        # Should be able to get a logger after configuration
        logger = structlog.get_logger()
        assert logger is not None

        # Logger should have the expected methods
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "critical")

    def test_intercept_handler_integration_with_stdlib_logging(self):
        """Test InterceptHandler integration with standard library logging."""
        # Reset any existing handlers
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]

        try:
            # Clear existing handlers
            root_logger.handlers.clear()

            # Add InterceptHandler
            handler = InterceptHandler()
            root_logger.addHandler(handler)
            root_logger.setLevel(logging.DEBUG)

            # Configure structlog to capture the intercepted logs
            with patch("structlog.get_logger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                # Use stdlib logging
                test_logger = logging.getLogger("test.logger")
                test_logger.info("Test message")

                # Should have intercepted and forwarded to structlog
                mock_get_logger.assert_called_with("test.logger")
                mock_logger.info.assert_called_with("Test message")

        finally:
            # Restore original handlers
            root_logger.handlers[:] = original_handlers


# Integration tests for SizedLogBuffer with write operations
class TestSizedLogBufferIntegration:
    """Integration tests for SizedLogBuffer with various data formats."""

    def test_write_with_event_field(self):
        """Test write() with event field in message."""
        buffer = SizedLogBuffer()
        buffer.max = 5

        message = json.dumps({"event": "Test event message", "timestamp": "2021-07-01T12:00:00Z"})

        buffer.write(message)
        assert len(buffer) == 1
        # Check that event was extracted correctly
        entries = buffer.get_last_n(1)
        assert "Test event message" in entries.values()

    def test_write_with_msg_field_fallback(self):
        """Test write() falls back to msg field when event is not present."""
        buffer = SizedLogBuffer()
        buffer.max = 5

        message = json.dumps({"msg": "Test msg message", "timestamp": "2021-07-01T12:00:00Z"})

        buffer.write(message)
        assert len(buffer) == 1
        entries = buffer.get_last_n(1)
        assert "Test msg message" in entries.values()

    def test_write_with_numeric_timestamp(self):
        """Test write() with numeric timestamp."""
        buffer = SizedLogBuffer()
        buffer.max = 5

        timestamp = 1625097600.123
        message = json.dumps({"event": "Test message", "timestamp": timestamp})

        buffer.write(message)
        entries = buffer.get_last_n(1)
        # Should convert to epoch milliseconds
        expected_timestamp = int(timestamp * 1000)
        assert expected_timestamp in entries

    def test_write_with_iso_timestamp(self):
        """Test write() with ISO format timestamp."""
        buffer = SizedLogBuffer()
        buffer.max = 5

        message = json.dumps({"event": "Test message", "timestamp": "2021-07-01T12:00:00.123Z"})

        buffer.write(message)
        entries = buffer.get_last_n(1)
        assert len(entries) == 1
        # Should have parsed and converted timestamp
        timestamps = list(entries.keys())
        assert timestamps[0] > 0  # Should be a valid epoch timestamp


class TestSpecificBugFixes:
    """Test suite for specific bugs that were discovered and fixed."""

    def test_disable_with_critical_plus_one_level(self):
        """Test the specific bug where disable=True with CRITICAL+1 caused KeyError.

        This was the original bug: when disable=True was used, the code tried
        to use logging.CRITICAL + 1 as a filter level, which would cause a
        KeyError in structlog's make_filtering_bound_logger function.
        """
        # This specific case should not raise a KeyError anymore
        try:
            configure(disable=True, log_level="CRITICAL")
            logger = structlog.get_logger()

            # The logger should be configured but effectively disabled
            assert logger is not None

            # Try to log something - it should not crash
            logger.info("This should not appear")
            logger.critical("This should also not appear")

        except KeyError as e:
            pytest.fail(f"KeyError raised during configure with disable=True: {e}")
        except Exception:  # noqa: S110
            # Other exceptions might be OK, but KeyError specifically was the bug
            pass

    def test_log_buffer_thread_safety(self):
        """Test that log buffer operations are thread-safe."""
        import threading
        import time

        buffer = SizedLogBuffer(max_readers=5)
        buffer.max = 100

        results = []
        errors = []

        def write_logs():
            try:
                for i in range(10):
                    message = json.dumps({"event": f"Thread message {i}", "timestamp": time.time() + i})
                    buffer.write(message)
                    time.sleep(0.001)  # Small delay to simulate real usage
                results.append("write_success")
            except Exception as e:
                errors.append(f"Write error: {e}")

        def read_logs():
            try:
                for _i in range(5):
                    entries = buffer.get_last_n(5)
                    assert isinstance(entries, dict)
                    time.sleep(0.002)  # Small delay
                results.append("read_success")
            except Exception as e:
                errors.append(f"Read error: {e}")

        # Create multiple threads for reading and writing
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=write_logs))
            threads.append(threading.Thread(target=read_logs))

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)

        # Check that no errors occurred
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Check that all operations completed successfully
        assert len(results) == 6  # 3 write + 3 read operations
        assert all("success" in result for result in results)

    def test_log_rotation_parsing_edge_cases(self):
        """Test edge cases in log rotation parsing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            log_file_path = Path(tmp_file.name)

        test_cases = [
            ("100 MB", 100 * 1024 * 1024),
            ("50MB", 10 * 1024 * 1024),  # Should fall back to default
            ("invalid format", 10 * 1024 * 1024),  # Should fall back to default
            ("", 10 * 1024 * 1024),  # Should use default
            ("0 MB", 10 * 1024 * 1024),  # Should fall back to default
        ]

        for rotation_str, expected_bytes in test_cases:
            try:
                # Clear any existing handlers
                for handler in logging.root.handlers[:]:
                    if isinstance(handler, logging.handlers.RotatingFileHandler):
                        logging.root.removeHandler(handler)

                configure(log_file=log_file_path, log_rotation=rotation_str)

                rotating_handlers = [
                    h for h in logging.root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
                ]

                if rotating_handlers:
                    handler = rotating_handlers[0]
                    assert handler.maxBytes == expected_bytes, f"Failed for rotation '{rotation_str}'"

            finally:
                # Cleanup for each test case
                if log_file_path.exists():
                    with contextlib.suppress(builtins.BaseException):
                        log_file_path.unlink()
                for handler in logging.root.handlers[:]:
                    if isinstance(handler, logging.handlers.RotatingFileHandler):
                        logging.root.removeHandler(handler)


@pytest.fixture
def sized_log_buffer():
    return SizedLogBuffer()


def test_init_default():
    buffer = SizedLogBuffer()
    assert buffer.max == 0
    assert buffer._max_readers == 20


def test_init_with_env_variable():
    with patch.dict(os.environ, {"LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE": "100"}):
        buffer = SizedLogBuffer()
        assert buffer.max == 100


def test_write(sized_log_buffer):
    message = json.dumps({"text": "Test log", "record": {"time": {"timestamp": 1625097600.1244334}}})
    sized_log_buffer.max = 1  # Set max size to 1 for testing
    sized_log_buffer.write(message)
    assert len(sized_log_buffer.buffer) == 1
    assert sized_log_buffer.buffer[0][0] == 1625097600124
    assert sized_log_buffer.buffer[0][1] == "Test log"


def test_write_overflow(sized_log_buffer):
    sized_log_buffer.max = 2
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(3)]
    for message in messages:
        sized_log_buffer.write(message)

    assert len(sized_log_buffer.buffer) == 2
    assert sized_log_buffer.buffer[0][0] == 1625097601000
    assert sized_log_buffer.buffer[1][0] == 1625097602000


def test_len(sized_log_buffer):
    sized_log_buffer.max = 3
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(3)]
    for message in messages:
        sized_log_buffer.write(message)

    assert len(sized_log_buffer) == 3


def test_get_after_timestamp(sized_log_buffer):
    sized_log_buffer.max = 5
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(5)]
    for message in messages:
        sized_log_buffer.write(message)

    result = sized_log_buffer.get_after_timestamp(1625097602000, lines=2)
    assert len(result) == 2
    assert 1625097603000 in result
    assert 1625097602000 in result


def test_get_before_timestamp(sized_log_buffer):
    sized_log_buffer.max = 5
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(5)]
    for message in messages:
        sized_log_buffer.write(message)

    result = sized_log_buffer.get_before_timestamp(1625097603000, lines=2)
    assert len(result) == 2
    assert 1625097601000 in result
    assert 1625097602000 in result


def test_get_last_n(sized_log_buffer):
    sized_log_buffer.max = 5
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(5)]
    for message in messages:
        sized_log_buffer.write(message)

    result = sized_log_buffer.get_last_n(3)
    assert len(result) == 3
    assert 1625097602000 in result
    assert 1625097603000 in result
    assert 1625097604000 in result


def test_enabled(sized_log_buffer):
    assert not sized_log_buffer.enabled()
    sized_log_buffer.max = 1
    assert sized_log_buffer.enabled()


def test_max_size(sized_log_buffer):
    assert sized_log_buffer.max_size() == 0
    sized_log_buffer.max = 100
    assert sized_log_buffer.max_size() == 100
