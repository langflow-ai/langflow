"""Unit tests for the logger module.

This test suite covers the functionality provided by the logger module,
including the SizedLogBuffer operations, logging configuration functions,
log format validation, asynchronous file sink behavior, and the intercept handler.
"""

import datetime
import json
import logging
import os
import tempfile
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from langflow.logging.logger import (
    DEFAULT_LOG_FORMAT,
    AsyncFileSink,
    InterceptHandler,
    SizedLogBuffer,
    configure,
    configure_container_logging,
    configure_standard_logging,
    is_valid_log_format,
    serialize_log,
)
from loguru import logger as loguru_logger

# The filter from your logger config
EXCLUDED_PATHS = ["/health", "/health_check", "/metrics"]


def log_filter(record):
    return not any(path in record["message"] for path in EXCLUDED_PATHS)


# =========================
# Tests for SizedLogBuffer
# =========================


@pytest.fixture
def sized_log_buffer() -> SizedLogBuffer:
    """Fixture to create a new SizedLogBuffer instance."""
    return SizedLogBuffer()


def test_init_default() -> None:
    """Test that the default initialization of SizedLogBuffer sets max to 0 and _max_readers to 20."""
    buffer: SizedLogBuffer = SizedLogBuffer()
    assert buffer.max == 0
    assert buffer._max_readers == 20


def test_init_with_env_variable() -> None:
    """Test that setting the LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE environment variable initializes max accordingly."""
    with patch.dict(os.environ, {"LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE": "100"}):
        buffer: SizedLogBuffer = SizedLogBuffer()
        assert buffer.max == 100


def test_write(sized_log_buffer: SizedLogBuffer) -> None:
    """Test that writing a log message stores the correct timestamp and text."""
    message: str = json.dumps({"text": "Test log", "record": {"time": {"timestamp": 1625097600.1244334}}})
    sized_log_buffer.max = 1  # Set max size to 1 for testing
    sized_log_buffer.write(message)
    assert len(sized_log_buffer.buffer) == 1
    # Verify timestamp conversion (multiplied by 1000 and cast to int)
    assert sized_log_buffer.buffer[0][0] == 1625097600124
    assert sized_log_buffer.buffer[0][1] == "Test log"


def test_write_overflow(sized_log_buffer: SizedLogBuffer) -> None:
    """Test that the buffer correctly overwrites old entries when max size is exceeded."""
    sized_log_buffer.max = 2
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(3)]
    for message in messages:
        sized_log_buffer.write(message)
    assert len(sized_log_buffer.buffer) == 2
    assert sized_log_buffer.buffer[0][0] == 1625097601000
    assert sized_log_buffer.buffer[1][0] == 1625097602000


def test_len(sized_log_buffer: SizedLogBuffer) -> None:
    """Test that the length of the buffer reflects the number of log messages written."""
    sized_log_buffer.max = 3
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(3)]
    for message in messages:
        sized_log_buffer.write(message)
    assert len(sized_log_buffer) == 3


def test_get_after_timestamp(sized_log_buffer: SizedLogBuffer) -> None:
    """Test retrieval of log messages after a given timestamp."""
    sized_log_buffer.max = 5
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(5)]
    for message in messages:
        sized_log_buffer.write(message)
    result: dict[int, str] = sized_log_buffer.get_after_timestamp(1625097602000, lines=2)
    assert len(result) == 2
    # Check that expected timestamps are present
    assert 1625097603000 in result
    assert 1625097602000 in result


def test_get_before_timestamp(sized_log_buffer: SizedLogBuffer) -> None:
    """Test retrieval of log messages before a given timestamp."""
    sized_log_buffer.max = 5
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(5)]
    for message in messages:
        sized_log_buffer.write(message)
    result: dict[int, str] = sized_log_buffer.get_before_timestamp(1625097603000, lines=2)
    assert len(result) == 2
    assert 1625097601000 in result
    assert 1625097602000 in result


def test_get_last_n(sized_log_buffer: SizedLogBuffer) -> None:
    """Test retrieval of the last n log messages from the buffer."""
    sized_log_buffer.max = 5
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(5)]
    for message in messages:
        sized_log_buffer.write(message)
    result: dict[int, str] = sized_log_buffer.get_last_n(3)
    assert len(result) == 3
    assert 1625097602000 in result
    assert 1625097603000 in result
    assert 1625097604000 in result


def test_enabled(sized_log_buffer: SizedLogBuffer) -> None:
    """Test the enabled function of the log buffer."""
    assert not sized_log_buffer.enabled()
    sized_log_buffer.max = 1
    assert sized_log_buffer.enabled()


def test_max_size(sized_log_buffer: SizedLogBuffer) -> None:
    """Test that max_size returns the correct maximum size value."""
    assert sized_log_buffer.max_size() == 0
    sized_log_buffer.max = 100
    assert sized_log_buffer.max_size() == 100


def test_get_write_lock(sized_log_buffer: SizedLogBuffer) -> None:
    """Test that get_write_lock returns a Lock instance."""
    lock: Lock = sized_log_buffer.get_write_lock()
    # Compare against the type of a newly created lock instance.
    assert isinstance(lock, type(Lock()))


# ================================
# Tests for logging configuration
# ================================


def test_configure_disables_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that calling configure with disable=True disables the logger."""
    disable_called = False

    def fake_disable(name: str) -> None:  # noqa: ARG001
        nonlocal disable_called
        disable_called = True

    monkeypatch.setattr(loguru_logger, "disable", fake_disable)
    configure(disable=True)
    assert disable_called


def test_configure_container_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that container logging configuration sets up logger.add correctly when LANGFLOW_LOG_FORMAT is not set."""
    add_calls: list[dict[str, Any]] = []

    def fake_add(sink: object, **kwargs: Any) -> None:  # noqa: ARG001
        add_calls.append(kwargs)

    monkeypatch.setattr(loguru_logger, "add", fake_add)
    monkeypatch.delenv("LANGFLOW_LOG_FORMAT", raising=False)
    configure_container_logging("DEBUG", None, env_mode="container")
    assert len(add_calls) >= 1
    call: dict[str, Any] = add_calls[0]
    assert call.get("level") == "DEBUG"
    assert call.get("format") == DEFAULT_LOG_FORMAT


def test_configure_standard_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that standard logging configuration applies logger.configure and logger.add properly."""
    captured_config: dict[str, Any] = {}

    def fake_configure(handlers: object) -> None:
        captured_config["handlers"] = handlers

    monkeypatch.setattr(loguru_logger, "configure", fake_configure)
    add_calls: list[dict[str, Any]] = []

    def fake_add(sink: object, **kwargs: Any) -> int:  # noqa: ARG001
        add_calls.append(kwargs)
        return 1

    monkeypatch.setattr(loguru_logger, "add", fake_add)
    monkeypatch.delenv("LANGFLOW_LOG_FORMAT", raising=False)
    temp_log_file: Path = Path(tempfile.gettempdir()) / "test_langflow.log"
    configure_standard_logging("INFO", temp_log_file, None, async_file=False)
    assert "handlers" in captured_config
    assert len(add_calls) >= 1
    for call in add_calls:
        assert call.get("level") == "INFO"


def test_configure_calls_standard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that calling configure in a non-container environment calls the standard logging configuration functions."""
    add_calls: list[dict[str, Any]] = []
    config_calls: list[Any] = []
    monkeypatch.setattr(loguru_logger, "remove", lambda: None)
    monkeypatch.setattr(loguru_logger, "add", lambda *args, **kwargs: add_calls.append(kwargs))  # noqa: ARG005
    monkeypatch.setattr(loguru_logger, "configure", lambda handlers: config_calls.append(handlers))

    # We'll add the functions to the module temporarily
    import sys
    from types import ModuleType

    # Create temporary module or get existing one
    logger_module = sys.modules.get("langflow.logging.logger", ModuleType("langflow.logging.logger"))

    monkeypatch.setattr(logger_module, "setup_uvicorn_logger", lambda: None, raising=False)
    monkeypatch.setattr(logger_module, "setup_gunicorn_logger", lambda: None, raising=False)

    temp_log_file: Path = Path(tempfile.gettempdir()) / "test_configure.log"
    configure(
        log_level="WARNING",
        log_file=temp_log_file,
        disable=False,
        log_env="noncontainer",
        log_format="%(message)s",
        async_file=False,
    )

    assert len(config_calls) > 0
    assert len(add_calls) > 0


def test_configure_with_env_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that configure uses the LANGFLOW_LOG_LEVEL environment variable when log_level is not provided."""
    monkeypatch.setenv("LANGFLOW_LOG_LEVEL", "INFO")
    add_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(loguru_logger, "add", lambda *args, **kwargs: add_calls.append(kwargs))  # noqa: ARG005
    configure(disable=False)
    levels = [call.get("level", "") for call in add_calls if "level" in call]
    assert any(level == "INFO" for level in levels)


def test_configure_standard_logging_invalid_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that configure_standard_logging falls back to DEFAULT_LOG_FORMAT if an invalid log format is provided."""
    monkeypatch.delenv("LANGFLOW_LOG_FORMAT", raising=False)
    add_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(loguru_logger, "add", lambda *args, **kwargs: add_calls.append(kwargs))  # noqa: ARG005
    temp_log_file: Path = Path(tempfile.gettempdir()) / "test_invalid_format.log"
    configure_standard_logging("INFO", temp_log_file, "invalid_format", async_file=False)
    for call in add_calls:
        assert call.get("format") == DEFAULT_LOG_FORMAT


# =======================================
# Additional tests for logger.py functions
# =======================================


def test_is_valid_log_format_valid() -> None:
    """Test that a valid log format string is accepted."""
    valid_format: str = "%(asctime)s - %(levelname)s - %(message)s"
    valid: bool = is_valid_log_format(valid_format)
    assert valid is True


def test_is_valid_log_format_invalid() -> None:
    """Test that an invalid log format string returns False when ValueError is raised."""
    invalid_format: str = "{time:invalid_format} - {message}"
    result: bool = is_valid_log_format(invalid_format)
    assert result is False


@pytest.mark.asyncio
async def test_async_file_sink_write() -> None:
    """Test the asynchronous writing of log messages using AsyncFileSink."""
    temp_log_file: Path = Path(tempfile.gettempdir()) / "test_async_sink.log"
    sink: AsyncFileSink = AsyncFileSink(temp_log_file)
    test_message: str = "Test async log message"
    await sink.write_async(test_message)
    await sink.complete()
    assert True


def test_intercept_handler_emit() -> None:
    """Test that the InterceptHandler correctly processes and logs a record."""
    handler: InterceptHandler = InterceptHandler()
    record: logging.LogRecord = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="test_path",
        lineno=10,
        msg="Test error message",
        args=(),
        exc_info=None,
    )
    try:
        handler.emit(record)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"InterceptHandler.emit raised an exception: {exc}")
    assert True


# ============================================
# Tests for serialize_log function
# ============================================


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("GET /health", False),
        ("POST /health_check", False),
        ("GET /metrics", False),
        ("Request to /api/v1/run", True),
        ("Normal log message", True),
    ],
)
def test_log_filter_excludes_known_paths(message, expected):
    """Test that the log_filter function correctly filters out known paths."""
    record = {"message": message}
    assert log_filter(record) == expected


def test_serialize_log_valid() -> None:
    """Test that serialize_log returns a valid JSON string representation of a given log record."""
    # Create a mock Loguru-style record that matches your function's expectations
    mock_time = datetime.datetime.now(datetime.timezone.utc)

    # Use SimpleNamespace objects for nested attributes that need to be accessed with dot notation
    level_obj = SimpleNamespace(name="DEBUG")
    process_obj = SimpleNamespace(id=1234)
    thread_obj = SimpleNamespace(id=5678, name="test_thread")

    # Build the record dictionary with proper structure
    mock_record = {
        "time": mock_time,
        "level": level_obj,
        "message": "Serialized log test",
        "module": "test_module",
        "function": "test_function",
        "line": 10,
        "process": process_obj,
        "thread": thread_obj,
        "exception": None,
    }

    # Call the function
    result = serialize_log(mock_record)

    # Parse the result to verify it's valid JSON
    parsed_result = json.loads(result)

    # Verify essential fields are present
    assert "timestamp" in parsed_result
    assert "time" in parsed_result
    assert "message" in parsed_result
    assert parsed_result["message"] == "Serialized log test"
    assert parsed_result["level"] == "DEBUG"
    assert parsed_result["module"] == "test_module"
    assert parsed_result["function"] == "test_function"
    assert parsed_result["line"] == 10
    assert parsed_result["process"] == 1234
    assert parsed_result["thread"] == "test_thread"


def create_mock_record(message="Test message", level="INFO", exception=None) -> dict:
    """Helper function to create a mock Loguru record."""
    mock_time = datetime.datetime.now(datetime.timezone.utc)
    level_obj = SimpleNamespace(name=level)
    process_obj = SimpleNamespace(id=1234)
    thread_obj = SimpleNamespace(id=5678, name="test_thread")

    return {
        "time": mock_time,
        "level": level_obj,
        "message": message,
        "module": "test_module",
        "function": "test_function",
        "line": 10,
        "process": process_obj,
        "thread": thread_obj,
        "exception": exception,
    }


def test_serialize_log_basic():
    """Test basic serialization with minimal fields."""
    mock_record = create_mock_record()

    result = serialize_log(mock_record, dev_mode=False)

    parsed = json.loads(result)
    assert parsed["message"] == "Test message"
    assert parsed["level"] == "INFO"
    assert parsed["module"] == "test_module"
    assert parsed["function"] == "test_function"
    assert parsed["exception"] is None


def test_serialize_log_with_exception_dev_mode():
    """Test serialization with exception info in development mode."""
    try:
        msg = "Test exception"
        raise ValueError(msg)
    except ValueError as e:
        exception_info = SimpleNamespace(type=type(e), value=e)

    mock_record = create_mock_record(exception=exception_info)

    result = serialize_log(mock_record, dev_mode=True)

    parsed = json.loads(result)
    assert parsed["exception"]["type"] == "ValueError"
    assert parsed["exception"]["value"] == "Test exception"


def test_serialize_log_with_exception_prod_mode():
    """Test that exceptions are null in production mode even when present."""
    try:
        msg = "Test exception"
        raise ValueError(msg)
    except ValueError as e:
        exception_info = SimpleNamespace(type=type(e), value=e)

    mock_record = create_mock_record(exception=exception_info)

    result = serialize_log(mock_record, dev_mode=False)

    parsed = json.loads(result)
    assert parsed["exception"] is None


def test_serialize_log_different_levels():
    """Test serialization with different log levels."""
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        mock_record = create_mock_record(level=level)

        result = serialize_log(mock_record, dev_mode=False)

        parsed = json.loads(result)
        assert parsed["level"] == level


def test_serialize_log_timestamp_format():
    """Test that timestamp is correctly formatted."""
    fixed_time = datetime.datetime(2023, 1, 15, 12, 30, 45, 123456, tzinfo=datetime.timezone.utc)
    mock_record = create_mock_record()
    mock_record["time"] = fixed_time

    result = serialize_log(mock_record, dev_mode=False)

    parsed = json.loads(result)
    assert parsed["timestamp"] == fixed_time.timestamp()
    assert parsed["time"] == "2023-01-15 12:30:45.123"


def test_serialize_log_with_non_standard_exception():
    """Test serialization with an exception that doesn't have the standard attributes."""

    # Create a mock exception without the standard type attribute
    class CustomException:
        def __str__(self):
            return "Custom exception string"

    exception_info = CustomException()
    mock_record = create_mock_record(exception=exception_info)

    result = serialize_log(mock_record, dev_mode=True)

    parsed = json.loads(result)
    assert "exception" in parsed
    assert parsed["exception"]["type"] is None
    assert parsed["exception"]["value"] == "Custom exception string"


def test_serialize_log_with_unicode_message():
    """Test serialization with Unicode characters in the message."""
    unicode_message = "测试消息 - こんにちは - مرحبا"
    mock_record = create_mock_record(message=unicode_message)

    result = serialize_log(mock_record, dev_mode=False)

    parsed = json.loads(result)
    assert parsed["message"] == unicode_message


def test_serialize_log_with_very_long_message():
    """Test serialization with a very long message."""
    long_message = "A" * 10000
    mock_record = create_mock_record(message=long_message)

    result = serialize_log(mock_record, dev_mode=False)

    parsed = json.loads(result)
    assert parsed["message"] == long_message
    assert len(parsed["message"]) == 10000
