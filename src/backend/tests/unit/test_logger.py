import pytest
import os
import json
from unittest.mock import patch
from langflow.logging.logger import SizedLogBuffer


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
    assert 1625097600124 == sized_log_buffer.buffer[0][0]
    assert "Test log" == sized_log_buffer.buffer[0][1]


def test_write_overflow(sized_log_buffer):
    sized_log_buffer.max = 2
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(3)]
    for message in messages:
        sized_log_buffer.write(message)

    assert len(sized_log_buffer.buffer) == 2
    assert 1625097601000 == sized_log_buffer.buffer[0][0]
    assert 1625097602000 == sized_log_buffer.buffer[1][0]


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
