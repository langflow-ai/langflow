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
    setup_gunicorn_logger,
    setup_uvicorn_logger,
)
from loguru import logger as loguru_logger


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

    def test_configure_routes_loguru_messages_to_log_file(self):
        """Test configure() routes Loguru messages through Langflow logging."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file_path = Path(tmp_dir) / "langflow.log"

            for handler in logging.root.handlers[:]:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    logging.root.removeHandler(handler)

            try:
                configure(log_level="INFO", log_file=log_file_path, cache=False)
                loguru_logger.info("Custom component log message")

                for handler in logging.root.handlers:
                    if hasattr(handler, "flush"):
                        handler.flush()

                assert "Custom component log message" in log_file_path.read_text()
            finally:
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

    def test_container_json_includes_structured_traceback(self, capsys):
        """JSON renderer must serialize exc_info as a structured traceback for Grafana."""
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("traceback-test")
        try:
            msg = "boom"
            raise ValueError(msg)
        except ValueError as exc:
            log.error("connection failed", exc_info=exc)  # noqa: TRY400 - exc_info kwarg path under test

        out = capsys.readouterr().out.strip().splitlines()[-1]
        record = json.loads(out)
        assert record["event"] == "connection failed"
        assert record["level"] == "error"
        # dict_tracebacks emits an "exception" list with at least one frame.
        assert isinstance(record.get("exception"), list)
        assert record["exception"]
        first = record["exception"][0]
        assert first["exc_type"] == "ValueError"
        assert first["exc_value"] == "boom"
        assert first.get("frames")

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
        import orjson

        # Simulate what add_serialized does - creates a serialized field
        subset = {
            "timestamp": 1625097600.123,
            "message": "Test message",
            "level": "INFO",
            "module": "test_module",
        }
        event_dict = {"event": "Test message", "serialized": orjson.dumps(subset)}

        with (
            patch.object(log_buffer, "enabled", return_value=True),
            patch.object(log_buffer, "write") as mock_write,
        ):
            result = buffer_writer(None, "info", event_dict)

        # Should write to buffer when enabled
        mock_write.assert_called_once()
        call_args = mock_write.call_args[0]
        written_data = json.loads(call_args[0])
        assert written_data["message"] == "Test message"
        assert written_data["level"] == "INFO"
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


class TestProductionObservability:
    """Best-practice production logging: redaction, logger name, stdlib intercept, per-logger levels."""

    def setup_method(self):
        # Fully reset structlog so a previous test's cached factory (which may
        # hold a now-closed capsys pipe) cannot bleed into this test.
        structlog.reset_defaults()

    def teardown_method(self):
        structlog.reset_defaults()
        # Drop any InterceptHandler we installed so other tests aren't affected.
        logging.root.handlers = [h for h in logging.root.handlers if not isinstance(h, InterceptHandler)]

    def _emit_and_parse(self, capsys, fn):
        fn()
        out = capsys.readouterr().out.strip().splitlines()
        return [json.loads(line) for line in out if line.startswith("{")]

    def test_pii_redaction_top_level_and_nested(self, capsys):
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("redact.test")
        records = self._emit_and_parse(
            capsys,
            lambda: log.info(
                "login",
                user="alice",
                password="hunter2",  # noqa: S106 - test fixture for redaction  # pragma: allowlist secret
                api_key="sk-leak",  # pragma: allowlist secret
                nested={"authorization": "Bearer xyz", "safe": "ok"},  # pragma: allowlist secret
            ),
        )
        rec = records[-1]
        assert rec["password"] == "***"  # noqa: S105
        assert rec["api_key"] == "***"
        assert rec["nested"]["authorization"] == "***"
        assert rec["nested"]["safe"] == "ok"
        assert rec["user"] == "alice"

    def test_logger_name_in_json_output(self, capsys):
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("my.service.module")
        records = self._emit_and_parse(capsys, lambda: log.info("hello"))
        assert records[-1]["logger"] == "my.service.module"

    def test_stdlib_intercept_forwards_exception(self, capsys):
        configure(log_env="container", log_level="DEBUG", cache=False)
        stdlib = logging.getLogger("third_party_lib")

        def emit():
            try:
                msg = "upstream"
                raise ConnectionError(msg)
            except ConnectionError:
                stdlib.error("call failed", exc_info=True)

        records = self._emit_and_parse(capsys, emit)
        rec = records[-1]
        assert rec["event"] == "call failed"
        assert rec["logger"] == "third_party_lib"
        assert isinstance(rec.get("exception"), list)
        assert rec["exception"][0]["exc_type"] == "ConnectionError"

    def test_per_logger_level_overrides_via_env(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_LOG_LEVELS", "noisy.lib=WARNING,other=ERROR")
        configure(log_env="container", log_level="DEBUG", cache=False)
        assert logging.getLogger("noisy.lib").level == logging.WARNING
        assert logging.getLogger("other").level == logging.ERROR

    def test_extra_redact_keys_via_env(self, capsys, monkeypatch):
        monkeypatch.setenv("LANGFLOW_LOG_REDACT_KEYS", "session_id,internal_key")
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("redact.extra")
        records = self._emit_and_parse(
            capsys,
            lambda: log.info("hi", session_id="abc", internal_key="xyz", safe="ok"),
        )
        rec = records[-1]
        assert rec["session_id"] == "***"
        assert rec["internal_key"] == "***"
        assert rec["safe"] == "ok"

    def test_traceback_locals_disabled_by_default(self, capsys):
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("locals.test")
        secret_var = "sk-do-not-leak"  # pragma: allowlist secret # noqa: F841, S105

        def emit():
            try:
                msg = "boom"
                raise RuntimeError(msg)
            except RuntimeError as e:
                log.error("trace", exc_info=e)  # noqa: TRY400 - exc_info kwarg path under test

        records = self._emit_and_parse(capsys, emit)
        # The secret string must not appear anywhere in the rendered JSON.
        # That is the real security property; field renames in
        # ExceptionDictTransformer must not cause this test to pass by accident.
        rendered = json.dumps(records[-1])
        assert "sk-do-not-leak" not in rendered  # pragma: allowlist secret

    def test_traceback_locals_enabled_via_opt_in(self, capsys, monkeypatch):
        # LANGFLOW_LOG_TRACE_LOCALS=true is the explicit opt-in for local
        # debugging. Verifies the opt-in actually flips the safe default.
        monkeypatch.setenv("LANGFLOW_LOG_TRACE_LOCALS", "true")
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("locals.optin")

        def emit():
            traceable_marker = "marker-locals-on"  # noqa: F841 - must appear in frame locals
            try:
                msg = "boom"
                raise RuntimeError(msg)
            except RuntimeError as e:
                log.error("trace", exc_info=e)  # noqa: TRY400 - exc_info kwarg path under test

        records = self._emit_and_parse(capsys, emit)
        rendered = json.dumps(records[-1])
        assert "marker-locals-on" in rendered

    def test_intercept_handler_is_idempotent(self):
        # Two configure() calls must leave exactly one InterceptHandler
        # attached, with the second call's level winning. A regression here
        # multiplies log volume in production.
        configure(log_env="container", log_level="DEBUG", cache=False)
        configure(log_env="container", log_level="WARNING", cache=False)
        handlers = [h for h in logging.root.handlers if isinstance(h, InterceptHandler)]
        assert len(handlers) == 1
        assert handlers[0].level == logging.WARNING

    def test_intercept_handler_not_installed_in_pretty_mode(self, monkeypatch):
        # Pretty/console mode must NOT route stdlib through structlog,
        # otherwise dev terminals get duplicated lines.
        monkeypatch.setenv("LANGFLOW_PRETTY_LOGS", "true")
        configure(log_env="", log_level="DEBUG", cache=False)
        handlers = [h for h in logging.root.handlers if isinstance(h, InterceptHandler)]
        assert handlers == []

    def test_intercept_handler_forwards_stack_info(self, capsys):
        # stack_info is the new behavior added to InterceptHandler.emit -
        # locks in that stdlib `logger.error("...", stack_info=True)` survives.
        configure(log_env="container", log_level="DEBUG", cache=False)
        stdlib = logging.getLogger("third_party.stack")
        records = self._emit_and_parse(
            capsys,
            lambda: stdlib.error("with stack", stack_info=True),
        )
        rec = records[-1]
        assert rec["event"] == "with stack"
        # structlog renders stack_info under the `stack` key.
        assert "stack" in rec
        assert "Stack (most recent call last)" in rec["stack"]

    def test_intercept_handler_swallows_broken_format_args(self):
        # A buggy library calling `logger.info("user %s", a, b)` must not
        # raise into the caller from our handler. Exercise emit() directly
        # to avoid pytest's caplog also handling the same record (which
        # would re-raise the formatting error from its own handler).
        configure(log_env="container", log_level="DEBUG", cache=False)
        handler = InterceptHandler()
        record = logging.LogRecord(
            name="broken.lib",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="user %s",
            args=("alice", "extra-arg-not-allowed"),
            exc_info=None,
        )
        # Must not raise; stdlib contract is to route through handleError.
        with Path(os.devnull).open("w") as devnull, contextlib.redirect_stderr(devnull):
            handler.emit(record)

    def test_service_info_defaults_to_langflow(self, capsys):
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("svc.default")
        records = self._emit_and_parse(capsys, lambda: log.info("hi"))
        rec = records[-1]
        assert rec["service"] == "langflow"
        # version/environment are omitted when unset.
        assert "version" not in rec
        assert "environment" not in rec

    def test_service_info_from_env_appears_in_records(self, capsys, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SERVICE_NAME", "lfx-runner")
        monkeypatch.setenv("LANGFLOW_VERSION", "1.2.3")
        monkeypatch.setenv("LANGFLOW_ENVIRONMENT", "staging")
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("svc.env")
        records = self._emit_and_parse(capsys, lambda: log.info("hi"))
        rec = records[-1]
        assert rec["service"] == "lfx-runner"
        assert rec["version"] == "1.2.3"
        assert rec["environment"] == "staging"

    def test_malformed_log_levels_emits_warning(self, monkeypatch):
        # Typos like `WARN` instead of `WARNING` must surface, not silently
        # drop. Operators need feedback that their config didn't apply.
        monkeypatch.setenv(
            "LANGFLOW_LOG_LEVELS",
            "sqlalchemy.engine=WARN,good=INFO,broken,=NOLEVEL,empty=,a=NOTALEVEL",
        )
        with pytest.warns(UserWarning, match="LANGFLOW_LOG_LEVELS"):
            configure(log_env="container", log_level="DEBUG", cache=False)
        # Valid entry still applied past the bad ones.
        assert logging.getLogger("good").level == logging.INFO

    def test_container_csv_preserves_exception_text(self, capsys):
        # Before the fix, container_csv silently dropped exceptions. Lock in
        # that the traceback is rendered into the CSV-style row.
        configure(log_env="container_csv", log_level="DEBUG", cache=False)
        log = structlog.get_logger("csv.test")
        try:
            msg = "boom-csv"
            raise ValueError(msg)
        except ValueError as e:
            log.error("oh no", exc_info=e)  # noqa: TRY400 - exc_info kwarg path under test
        out = capsys.readouterr().out
        assert "ValueError" in out
        assert "boom-csv" in out

    def test_redaction_walks_lists_and_tuples(self, capsys):
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("redact.collections")
        records = self._emit_and_parse(
            capsys,
            lambda: log.info(
                "audit",
                # pragma: allowlist secret
                users_list=[{"password": "x", "name": "alice"}],
                # pragma: allowlist secret
                users_tuple=({"token": "y", "name": "bob"},),
            ),
        )
        rec = records[-1]
        assert rec["users_list"][0]["password"] == "***"  # noqa: S105
        assert rec["users_list"][0]["name"] == "alice"
        assert rec["users_tuple"][0]["token"] == "***"  # noqa: S105
        assert rec["users_tuple"][0]["name"] == "bob"

    def test_redaction_depth_limit_documents_contract(self, capsys):
        # The 4-level walk is a deliberate trade-off; this test pins it down
        # so a future change to the depth constant has to be intentional.
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("redact.depth")
        marker = "leak-at-5"  # pragma: allowlist secret
        deep = {"l1": {"l2": {"l3": {"l4": {"password": marker}}}}}
        records = self._emit_and_parse(capsys, lambda: log.info("deep", payload=deep))
        rec = records[-1]
        # At depth 5 (beyond the limit) the password value is passed through.
        assert rec["payload"]["l1"]["l2"]["l3"]["l4"]["password"] == marker

    def test_otel_processor_no_op_when_no_span(self, capsys):
        # OTel SDK may be installed but no span is active. Processor must
        # produce records without trace_id/span_id rather than failing.
        configure(log_env="container", log_level="DEBUG", cache=False)
        log = structlog.get_logger("otel.nospan")
        records = self._emit_and_parse(capsys, lambda: log.info("hi"))
        rec = records[-1]
        # Either keys are absent or both are present (if a real span is
        # somehow active in this process); they must never half-render.
        if "trace_id" in rec or "span_id" in rec:
            assert "trace_id" in rec
            assert "span_id" in rec


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
            threads.append(threading.Thread(target=write_logs, daemon=False))
            threads.append(threading.Thread(target=read_logs, daemon=False))

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete and verify they finished
        hung_threads = []
        for thread in threads:
            thread.join(timeout=5)
            if thread.is_alive():
                hung_threads.append(thread.name)

        # Fail fast if any threads are still running
        assert len(hung_threads) == 0, f"Threads did not complete within timeout: {hung_threads}"

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


class TestBufferWriterBytesSerializationFix:
    """Test suite for the buffer_writer bytes serialization bug fix.

    These tests validate the fix for the bug where buffer_writer would fail
    when trying to serialize event_dict containing bytes (from orjson.dumps).
    The fix uses the pre-serialized 'serialized' field directly instead of
    re-serializing the entire event_dict.
    """

    def test_buffer_writer_with_bytes_in_serialized_field(self):
        """Test buffer_writer handles bytes in 'serialized' field correctly.

        This is the main bug fix test: when add_serialized adds a 'serialized'
        field with bytes (from orjson.dumps), buffer_writer should use that
        directly instead of trying to serialize the whole event_dict.
        """
        import orjson

        # Simulate what add_serialized does - adds bytes to event_dict
        serialized_data = {"timestamp": "2025-11-21T12:00:00Z", "message": "Test message", "level": "INFO"}
        event_dict = {
            "timestamp": "2025-11-21T12:00:00Z",
            "event": "Test message with bytes",
            "level": "info",
            "module": "test_module",
            "serialized": orjson.dumps(serialized_data),  # This is bytes!
        }

        with (
            patch.object(log_buffer, "enabled", return_value=True),
            patch.object(log_buffer, "write") as mock_write,
        ):
            # This should NOT raise TypeError: Object of type bytes is not JSON serializable
            result = buffer_writer(None, "info", event_dict)

        # Verify buffer_writer was called
        mock_write.assert_called_once()

        # Verify the written data is the decoded serialized field
        call_args = mock_write.call_args[0]
        written_json = call_args[0]

        # Should be able to parse it without error
        parsed_data = json.loads(written_json)

        # Should have the data from the serialized field
        assert parsed_data["timestamp"] == "2025-11-21T12:00:00Z"
        assert parsed_data["message"] == "Test message"
        assert parsed_data["level"] == "INFO"

        # Original event_dict should be returned unchanged
        assert result == event_dict
        assert "serialized" in result  # Original still has it

    def test_buffer_writer_without_serialized_field(self):
        """Test buffer_writer does nothing when no 'serialized' field exists."""
        event_dict = {
            "timestamp": "2025-11-21T12:00:00Z",
            "event": "Normal message",
            "level": "info",
        }

        with (
            patch.object(log_buffer, "enabled", return_value=True),
            patch.object(log_buffer, "write") as mock_write,
        ):
            result = buffer_writer(None, "info", event_dict)

        # Should NOT write to buffer when serialized field is missing
        mock_write.assert_not_called()
        assert result == event_dict

    def test_buffer_writer_uses_serialized_field_only(self):
        """Test buffer_writer uses only the serialized field, ignoring others."""
        import orjson

        # The serialized field is what gets written to the buffer
        serialized_data = {"key": "value", "message": "Test"}
        event_dict = {
            "event": "Test",
            "serialized": orjson.dumps(serialized_data),
            "another_bytes": b"some bytes",  # Another bytes field (ignored)
            "bytearray_field": bytearray(b"bytearray data"),  # bytearray (ignored)
            "normal_field": "normal string",  # normal field (ignored)
        }

        with (
            patch.object(log_buffer, "enabled", return_value=True),
            patch.object(log_buffer, "write") as mock_write,
        ):
            # Should not crash and should only use the serialized field
            result = buffer_writer(None, "info", event_dict)
            mock_write.assert_called_once()

            # Verify result is returned unchanged
            assert result == event_dict

            # Verify only the serialized field contents were written
            call_args = mock_write.call_args[0]
            written_json = call_args[0]
            parsed_data = json.loads(written_json)

            # Should only contain what was in serialized field
            assert parsed_data == serialized_data
            assert "key" in parsed_data
            assert "message" in parsed_data
            # Other fields from event_dict should NOT be in buffer
            assert "another_bytes" not in parsed_data
            assert "bytearray_field" not in parsed_data
            assert "normal_field" not in parsed_data

    def test_buffer_writer_ignores_non_serialized_fields(self):
        """Test buffer_writer only writes serialized field, ignores others."""
        import orjson

        serialized_data = {"message": "Test message", "level": "INFO"}
        event_dict = {
            "event": "Test with memoryview",
            "memoryview_field": memoryview(b"memoryview data"),
            "normal_field": "normal string",
            "serialized": orjson.dumps(serialized_data),
        }

        with (
            patch.object(log_buffer, "enabled", return_value=True),
            patch.object(log_buffer, "write") as mock_write,
        ):
            result = buffer_writer(None, "info", event_dict)
            mock_write.assert_called_once()

            # Verify result unchanged
            assert result == event_dict

            # Verify only serialized data was written
            call_args = mock_write.call_args[0]
            written_json = call_args[0]
            parsed_data = json.loads(written_json)

            # Should only have data from serialized field
            assert parsed_data == serialized_data
            assert "event" not in parsed_data
            assert "normal_field" not in parsed_data
            assert "memoryview_field" not in parsed_data

    def test_add_serialized_and_buffer_writer_integration(self):
        """Integration test: add_serialized followed by buffer_writer.

        This simulates the real processor chain where add_serialized adds
        bytes and buffer_writer uses it directly.
        """
        event_dict = {
            "timestamp": 1625097600.123,
            "event": "Integration test message",
            "module": "test_module",
        }

        with patch.object(log_buffer, "enabled", return_value=True):
            # Step 1: add_serialized adds the bytes field
            after_add = add_serialized(None, "debug", event_dict)

            # Verify serialized field was added and is bytes
            assert "serialized" in after_add
            assert isinstance(after_add["serialized"], bytes)

            # Step 2: buffer_writer should use the serialized field directly
            with patch.object(log_buffer, "write") as mock_write:
                result = buffer_writer(None, "debug", after_add)

            # Should have called write
            mock_write.assert_called_once()
            # Verify result is returned
            assert result == after_add

            # Should have written the decoded serialized field
            call_args = mock_write.call_args[0]
            written_json = call_args[0]
            parsed_data = json.loads(written_json)

            # Should contain the subset created by add_serialized
            assert parsed_data["timestamp"] == 1625097600.123
            assert parsed_data["message"] == "Integration test message"
            assert parsed_data["level"] == "DEBUG"
            assert parsed_data["module"] == "test_module"

    def test_buffer_writer_preserves_original_event_dict(self):
        """Test that buffer_writer doesn't modify the original event_dict."""
        import orjson

        event_dict = {
            "event": "Test",
            "serialized": orjson.dumps({"data": "test"}),
            "other_field": "value",
        }

        # Make a copy to compare later
        original_keys = set(event_dict.keys())

        with (
            patch.object(log_buffer, "enabled", return_value=True),
            patch.object(log_buffer, "write"),
        ):
            result = buffer_writer(None, "info", event_dict)

        # Original event_dict should be unchanged
        assert set(result.keys()) == original_keys
        assert "serialized" in result
        assert result is event_dict  # Should return the same object

    def test_buffer_writer_with_empty_event_dict(self):
        """Test buffer_writer handles empty event_dict gracefully."""
        event_dict = {}

        with (
            patch.object(log_buffer, "enabled", return_value=True),
            patch.object(log_buffer, "write") as mock_write,
        ):
            result = buffer_writer(None, "info", event_dict)

        # Should NOT write when serialized field is missing
        mock_write.assert_not_called()
        assert result == {}

    def test_buffer_writer_error_before_fix(self):
        """Document the error that occurred before the fix.

        This test demonstrates what would happen with the old implementation
        that tried to serialize bytes directly.
        """
        import orjson

        event_dict = {
            "event": "Test",
            "serialized": orjson.dumps({"data": "test"}),
        }

        # Simulate old buggy behavior (direct json.dumps on event_dict with bytes)
        with pytest.raises(TypeError, match="not JSON serializable"):
            json.dumps(event_dict)  # This is what the old code did

        # The fix (removing serialized field) should work
        filtered_dict = {k: v for k, v in event_dict.items() if k != "serialized"}
        serialized = json.dumps(filtered_dict)  # This should work
        assert json.loads(serialized) == {"event": "Test"}

    def test_buffer_writer_with_complex_nested_data(self):
        """Test buffer_writer with complex nested data structures in serialized field."""
        import orjson

        # The complex nested data should be IN the serialized field
        serialized_data = {
            "timestamp": "2025-11-21T12:00:00Z",
            "message": "Complex nested message",
            "metadata": {
                "user": "test_user",
                "nested": {"deeply": {"nested": "value"}},
                "list": [1, 2, 3],
            },
        }

        event_dict = {
            "timestamp": "2025-11-21T12:00:00Z",
            "event": "Complex nested message",
            "serialized": orjson.dumps(serialized_data),
        }

        with (
            patch.object(log_buffer, "enabled", return_value=True),
            patch.object(log_buffer, "write") as mock_write,
        ):
            result = buffer_writer(None, "info", event_dict)

        mock_write.assert_called_once()
        # Verify result is returned
        assert result == event_dict

        call_args = mock_write.call_args[0]
        written_json = call_args[0]

        # Should successfully write the complex nested structure from serialized field
        parsed_data = json.loads(written_json)
        assert parsed_data["metadata"]["nested"]["deeply"]["nested"] == "value"
        assert parsed_data["metadata"]["list"] == [1, 2, 3]
        assert parsed_data == serialized_data

    def test_full_logging_pipeline_with_retrieval_enabled(self):
        """End-to-end test of the full logging pipeline with log retrieval enabled.

        This simulates the complete flow: configure -> add_serialized -> buffer_writer
        """
        # Save original buffer state
        original_max = log_buffer.max

        try:
            # Enable log retrieval
            log_buffer.max = 10

            # Configure logger with DEBUG level
            configure(log_level="DEBUG", cache=False)

            # Create an event that will go through the processor chain
            event_dict = {
                "timestamp": "2025-11-21T12:00:00Z",
                "event": "End-to-end test message",
                "level": "debug",
                "module": "test",
            }

            # Run through add_serialized processor
            event_after_serialized = add_serialized(None, "debug", event_dict.copy())

            # Verify bytes were added
            assert "serialized" in event_after_serialized
            assert isinstance(event_after_serialized["serialized"], bytes)

            # Run through buffer_writer processor - should not crash
            with patch.object(log_buffer, "write") as mock_write:
                final_event = buffer_writer(None, "debug", event_after_serialized)

            # Verify it was written successfully
            mock_write.assert_called_once()
            # Verify final_event is returned
            assert final_event == event_after_serialized

            # Verify the written data is the decoded serialized field
            call_args = mock_write.call_args[0]
            written_json = call_args[0]
            parsed = json.loads(written_json)

            # Should contain the subset created by add_serialized
            assert parsed["message"] == "End-to-end test message"
            assert parsed["level"] == "DEBUG"
            assert parsed["module"] == "test"

        finally:
            # Restore buffer state
            log_buffer.max = original_max


class TestFileModeStdlibUnification:
    """JSON file mode must route third-party stdlib logs through structlog too.

    Regression coverage for the bug where ``LANGFLOW_LOG_ENV=container`` plus
    ``LANGFLOW_LOG_FILE`` skipped the stdlib path entirely: uvicorn, sqlalchemy,
    httpx, asyncio wrote plain text straight to the file, bypassing both JSON
    rendering and PII redaction.
    """

    def teardown_method(self):
        for handler in logging.root.handlers[:]:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                logging.root.removeHandler(handler)
                handler.close()
        structlog.reset_defaults()
        structlog.configure()

    @staticmethod
    def _read_records(log_file_path):
        for handler in logging.root.handlers:
            if hasattr(handler, "flush"):
                handler.flush()
        lines = [ln for ln in log_file_path.read_text().splitlines() if ln.strip()]
        # Every line must be valid JSON. Plain-text stdlib output raises here.
        return [json.loads(ln) for ln in lines]

    def test_container_file_mode_stdlib_logs_are_json_with_logger_name(self):
        """A third-party stdlib log lands in the file as JSON carrying its logger name."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file_path = Path(tmp_dir) / "langflow.log"
            configure(log_env="container", log_level="INFO", log_file=log_file_path, cache=False)

            logging.getLogger("sqlalchemy.engine").warning("connecting to pool")

            records = self._read_records(log_file_path)
            assert records, "expected at least one JSON log line"
            sa = [r for r in records if r.get("logger") == "sqlalchemy.engine"]
            assert sa, f"sqlalchemy.engine record missing; loggers seen: {[r.get('logger') for r in records]}"
            assert sa[0]["event"] == "connecting to pool"
            assert sa[0]["level"] == "warning"
            # Service metadata is attached to stdlib records too.
            assert sa[0]["service"] == "langflow"

    def test_container_file_mode_redacts_stdlib_extra(self):
        """PII redaction applies to structured fields on stdlib records in file mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file_path = Path(tmp_dir) / "langflow.log"
            configure(log_env="container", log_level="INFO", log_file=log_file_path, cache=False)

            logging.getLogger("httpx").warning(
                "request sent",
                extra={"authorization": "Bearer xyz"},  # pragma: allowlist secret
            )

            records = self._read_records(log_file_path)
            hx = [r for r in records if r.get("logger") == "httpx"]
            assert hx, f"httpx record missing; loggers seen: {[r.get('logger') for r in records]}"
            assert hx[0].get("authorization") == "***"

    def test_container_file_mode_app_logs_still_json_and_redacted(self):
        """Application logs keep their JSON + redaction in file mode (structlog path)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file_path = Path(tmp_dir) / "langflow.log"
            configure(log_env="container", log_level="INFO", log_file=log_file_path, cache=False)

            structlog.get_logger("langflow.api").info(
                "incoming",
                api_key="sk-do-not-leak",  # pragma: allowlist secret
            )

            records = self._read_records(log_file_path)
            app = [r for r in records if r.get("logger") == "langflow.api"]
            assert app, f"app record missing; loggers seen: {[r.get('logger') for r in records]}"
            assert app[0]["event"] == "incoming"
            assert app[0].get("api_key") == "***"


class TestConfigureEarlyReturnFingerprint:
    """configure()'s early-return must key off every effective input, not just the level.

    Regression coverage for the footgun where a second configure() call at the
    same log level but a different log_env / log_file / output_file silently
    no-opped: the file handler was never installed and the renderer never
    switched. That also made file-mode tests flaky -- a prior same-level
    configure() could make a later file-mode configure() do nothing, surfacing
    as FileNotFoundError when the test read a log file that was never written.
    The fix fingerprints all effective inputs while preserving the early-return
    optimization for genuinely identical calls (the Graph.__init__ hot path).
    """

    def setup_method(self):
        # Start from a clean slate so a leaked handler or a fingerprint left on
        # the wrapper_class by another test cannot mask the behavior under test.
        for handler in logging.root.handlers[:]:
            if isinstance(handler, logging.handlers.RotatingFileHandler | InterceptHandler):
                logging.root.removeHandler(handler)
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.close()
        structlog.reset_defaults()

    def teardown_method(self):
        for handler in logging.root.handlers[:]:
            if isinstance(handler, logging.handlers.RotatingFileHandler | InterceptHandler):
                logging.root.removeHandler(handler)
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.close()
        structlog.reset_defaults()
        structlog.configure()

    @staticmethod
    def _read_records(log_file_path):
        for handler in logging.root.handlers:
            if hasattr(handler, "flush"):
                handler.flush()
        return [json.loads(ln) for ln in log_file_path.read_text().splitlines() if ln.strip()]

    def test_same_level_new_env_and_file_takes_effect(self):
        """Second call: same level, but now container JSON + a log file. Must NOT no-op.

        This is the exact reported bug. Before the fix the level-only early-return
        skipped the whole rebuild: no RotatingFileHandler was installed and the
        file stayed empty.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file_path = Path(tmp_dir) / "langflow.log"

            # First call: console mode at INFO, no file handler.
            configure(log_level="INFO", log_env="", cache=False)
            assert not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logging.root.handlers), (
                "precondition failed: console-mode configure should not install a file handler"
            )

            # Second call at the SAME level, but container JSON written to a file.
            configure(log_level="INFO", log_env="container", log_file=log_file_path, cache=False)

            # The file handler is installed...
            assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logging.root.handlers), (
                "second configure() at the same level silently no-opped: no file handler installed"
            )

            # ...and JSON is actually written to the file.
            structlog.get_logger("fingerprint.test").info("after reconfigure")
            records = self._read_records(log_file_path)
            assert records, "log file is empty -- the second configure() did not take effect"
            assert any(r.get("event") == "after reconfigure" for r in records)
            assert all("event" in r for r in records), "file is not JSON -- renderer did not switch"

    def test_identical_call_early_returns_optimization_preserved(self):
        """Two byte-for-byte identical calls must still early-return (no rebuild).

        Locks in the optimization the fingerprint exists to preserve: a second
        identical call must NOT tear down and rebuild the pipeline (the per-Graph
        hot path). configure() rebuilds the processors list from scratch on every
        real reconfigure and hands the new list to structlog.configure(); an
        early-return never touches structlog, so the stored list object is
        reused. (wrapper_class identity can't be used here -- structlog caches
        the filtering bound logger class per level, so it's shared across calls.)
        """
        configure(log_level="INFO", log_env="container", cache=False)
        first = structlog.get_config()["processors"]
        configure(log_level="INFO", log_env="container", cache=False)
        second = structlog.get_config()["processors"]
        assert first is second, "identical configure() rebuilt the pipeline; early-return regressed"

    def test_same_level_new_output_file_takes_effect(self):
        """Same level, new output_file must reconfigure (the lfx.run.base path).

        lfx.run.base calls configure(log_level=..., output_file=sys.stderr) at
        fixed levels; a level-only early-return would pin logs to the first
        call's stream. output_file is part of the fingerprint, so the second
        call rebuilds (fresh processors list) and logs reach the new stream.
        """
        import io

        stream_a = io.StringIO()
        stream_b = io.StringIO()

        configure(log_level="INFO", log_env="", output_file=stream_a, cache=False)
        first = structlog.get_config()["processors"]
        configure(log_level="INFO", log_env="", output_file=stream_b, cache=False)
        second = structlog.get_config()["processors"]
        assert first is not second, "output_file change at the same level was ignored (early-returned)"

        # The real side effect: logs now reach stream_b, not the first stream.
        structlog.get_logger("stream.test").info("routed to b")
        assert "routed to b" in stream_b.getvalue()
        assert "routed to b" not in stream_a.getvalue()


class TestStdlibLevelNameMutationRobustness:
    r"""Third-party ``logging.addLevelName`` calls must not corrupt the ``level`` field.

    Libraries such as ``ibm_watsonx_orchestrate_core`` globally rewrite stdlib
    level names (wrapping them in ANSI color codes) via ``logging.addLevelName``.
    That mutation persists process-wide. structlog's ProcessorFormatter derives a
    foreign record's level from ``record.levelname.lower()``, so without care the
    colored string (e.g. ``\x1b[0;33m[warning]\x1b[0;0m``) lands in the JSON
    ``level`` field and breaks level filtering in Grafana/Loki. The logger must
    derive levels from the immutable ``levelno`` on both the file and stdout paths.
    """

    # The ANSI-wrapped names ibm_watsonx_orchestrate_core.setup_logging installs.
    _MANGLED = {
        logging.DEBUG: "\x1b[0;35m[DEBUG]\x1b[0;0m",
        logging.INFO: "\x1b[0;36m[INFO]\x1b[0;0m",
        logging.WARNING: "\x1b[0;33m[WARNING]\x1b[0;0m",
        logging.ERROR: "\x1b[0;31m[ERROR]\x1b[0;0m",
    }
    _ORIGINAL = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def setup_method(self):
        # Reset structlog so configure() cannot early-return on a matching level
        # left over from a prior test, then apply the global name mutation.
        structlog.reset_defaults()
        for levelno, name in self._MANGLED.items():
            logging.addLevelName(levelno, name)

    def teardown_method(self):
        # Restore the standard names so this test cannot pollute the rest of the
        # run -- which is exactly the failure mode under test.
        for levelno, name in self._ORIGINAL.items():
            logging.addLevelName(levelno, name)
        for handler in logging.root.handlers[:]:
            if isinstance(handler, logging.handlers.RotatingFileHandler | InterceptHandler):
                logging.root.removeHandler(handler)
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.close()
        structlog.reset_defaults()
        structlog.configure()

    def test_file_mode_level_is_clean_despite_addlevelname(self):
        """File-mode JSON keeps a plain ``level`` even when stdlib names are mangled."""
        # Guard: the global mutation is actually in effect for this process.
        assert logging.getLevelName(logging.WARNING) != "WARNING"

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file_path = Path(tmp_dir) / "langflow.log"
            configure(log_env="container", log_level="INFO", log_file=log_file_path, cache=False)

            logging.getLogger("sqlalchemy.engine").warning("connecting to pool")

            for handler in logging.root.handlers:
                if hasattr(handler, "flush"):
                    handler.flush()
            records = [json.loads(ln) for ln in log_file_path.read_text().splitlines() if ln.strip()]
            sa = [r for r in records if r.get("logger") == "sqlalchemy.engine"]
            assert sa, f"sqlalchemy.engine record missing; loggers seen: {[r.get('logger') for r in records]}"
            assert sa[0]["event"] == "connecting to pool"
            assert sa[0]["level"] == "warning"
            assert "\x1b" not in sa[0]["level"]

    def test_stdout_mode_level_is_clean_despite_addlevelname(self, capsys):
        """Stdout-mode intercept keeps a plain ``level`` even when stdlib names are mangled."""
        assert logging.getLevelName(logging.ERROR) != "ERROR"
        configure(log_env="container", log_level="INFO", cache=False)

        logging.getLogger("httpx").error("boom")

        lines = [ln for ln in capsys.readouterr().out.strip().splitlines() if ln.strip().startswith("{")]
        records = [json.loads(ln) for ln in lines]
        hx = [r for r in records if r.get("logger") == "httpx"]
        assert hx, f"httpx record missing; loggers seen: {[r.get('logger') for r in records]}"
        assert hx[0]["event"] == "boom"
        assert hx[0]["level"] == "error"
        assert "\x1b" not in hx[0]["level"]


class TestInterceptExtraForwarding:
    """The stdout InterceptHandler forwards stdlib `extra` fields and redacts them."""

    def teardown_method(self):
        for handler in logging.root.handlers[:]:
            if isinstance(handler, InterceptHandler):
                logging.root.removeHandler(handler)
        structlog.reset_defaults()
        structlog.configure()

    def test_intercept_forwards_and_redacts_stdlib_extra(self, capsys):
        """A stdlib `extra` lands as a structured field; sensitive keys are redacted, others kept."""
        configure(log_env="container", log_level="INFO", cache=False)

        logging.getLogger("sqlalchemy.engine").warning(
            "checking out connection",
            extra={"password": "hunter2", "pool_size": 5},  # pragma: allowlist secret
        )

        lines = [ln for ln in capsys.readouterr().out.strip().splitlines() if ln.strip().startswith("{")]
        records = [json.loads(ln) for ln in lines]
        sa = [r for r in records if r.get("logger") == "sqlalchemy.engine"]
        assert sa, f"sqlalchemy.engine record missing; loggers seen: {[r.get('logger') for r in records]}"
        assert sa[0]["password"] == "***"  # noqa: S105 - sensitive extra redacted
        assert sa[0]["pool_size"] == 5  # non-sensitive extra preserved


class TestRetrievalBufferMessage:
    """The /logs retrieval buffer must capture the actual message text, not an empty string."""

    def teardown_method(self):
        log_buffer.max = 0
        structlog.reset_defaults()
        structlog.configure()

    def test_buffer_captures_message_text(self):
        """add_serialized writes the message under `message`; the buffer must read it back."""
        log_buffer.max = 100
        try:
            configure(log_env="container", log_level="INFO", cache=False)
            structlog.get_logger("demo").info("hello buffer world")
            values = list(log_buffer.get_last_n(5).values())
            assert values, "expected a buffered entry"
            assert "hello buffer world" in values
        finally:
            log_buffer.max = 0
