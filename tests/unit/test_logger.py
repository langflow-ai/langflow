import pytest
import os
import json
from collections import OrderedDict
from unittest.mock import patch
from langflow.utils.logger import SizedLogBuffer  # Replace 'your_module' with the actual module name


@pytest.fixture
def sized_log_buffer():
    return SizedLogBuffer()


def test_init_default():
    buffer = SizedLogBuffer()
    assert buffer.max == 0
    assert buffer._max_readers == 20
    assert isinstance(buffer.buffer, OrderedDict)


def test_init_with_env_variable():
    with patch.dict(os.environ, {"LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE": "100"}):
        buffer = SizedLogBuffer()
        assert buffer.max == 100


def test_write(sized_log_buffer):
    message = json.dumps({"text": "Test log", "record": {"time": {"timestamp": 1625097600}}})
    sized_log_buffer.max = 1  # Set max size to 1 for testing
    sized_log_buffer.write(message)
    assert len(sized_log_buffer.buffer) == 1
    assert 1625097600 in sized_log_buffer.buffer
    assert sized_log_buffer.buffer[1625097600] == "Test log"


def test_write_overflow(sized_log_buffer):
    sized_log_buffer.max = 2
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(3)]
    for message in messages:
        sized_log_buffer.write(message)

    assert len(sized_log_buffer.buffer) == 2
    assert 1625097601 in sized_log_buffer.buffer
    assert 1625097602 in sized_log_buffer.buffer


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

    result = sized_log_buffer.get_after_timestamp(1625097602, lines=2)
    assert len(result) == 2
    assert 1625097603 in result
    assert 1625097602 in result


def test_get_before_timestamp(sized_log_buffer):
    sized_log_buffer.max = 5
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(5)]
    for message in messages:
        sized_log_buffer.write(message)

    result = sized_log_buffer.get_before_timestamp(1625097603, lines=2)
    assert len(result) == 2
    assert 1625097601 in result
    assert 1625097602 in result


def test_get_last_n(sized_log_buffer):
    sized_log_buffer.max = 5
    messages = [json.dumps({"text": f"Log {i}", "record": {"time": {"timestamp": 1625097600 + i}}}) for i in range(5)]
    for message in messages:
        sized_log_buffer.write(message)

    result = sized_log_buffer.get_last_n(3)
    assert len(result) == 3
    assert 1625097602 in result
    assert 1625097603 in result
    assert 1625097604 in result


def test_enabled(sized_log_buffer):
    assert not sized_log_buffer.enabled()
    sized_log_buffer.max = 1
    assert sized_log_buffer.enabled()


def test_max_size(sized_log_buffer):
    assert sized_log_buffer.max_size() == 0
    sized_log_buffer.max = 100
    assert sized_log_buffer.max_size() == 100
