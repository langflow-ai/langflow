"""Tests for the gunicorn logging wiring in ``langflow.server``.

``Logger`` used to attach an ``InterceptHandler`` to ``gunicorn.error`` and
``gunicorn.access`` unconditionally. With a log file configured, structlog
resolves those names back to the same stdlib loggers, so every intercepted
record was handed straight back to the handler that intercepted it.
"""

import logging

import pytest
import structlog
from gunicorn.config import Config
from langflow.server import Logger
from lfx.log.logger import InterceptHandler, configure

GUNICORN_LOGGERS = ("gunicorn.error", "gunicorn.access")


@pytest.fixture(autouse=True)
def _restore_logging_state():
    """Put back the process-wide logging state these tests rewire."""
    original_root_handlers = list(logging.root.handlers)
    original_gunicorn_state = {
        name: (list(logging.getLogger(name).handlers), logging.getLogger(name).level, logging.getLogger(name).propagate)
        for name in GUNICORN_LOGGERS
    }

    yield

    structlog.reset_defaults()
    logging.root.handlers = original_root_handlers
    for name, (handlers, level, propagate) in original_gunicorn_state.items():
        gunicorn_logger = logging.getLogger(name)
        gunicorn_logger.handlers = handlers
        gunicorn_logger.setLevel(level)
        gunicorn_logger.propagate = propagate


def test_intercepts_when_structlog_writes_to_the_stream():
    """Without a log file the print factory cannot cycle, so interception stands."""
    configure(log_level="ERROR", cache=False)

    Logger(Config())

    for name in GUNICORN_LOGGERS:
        handlers = logging.getLogger(name).handlers
        assert len(handlers) == 1
        assert isinstance(handlers[0], InterceptHandler)


def test_propagates_instead_of_intercepting_when_a_log_file_is_configured(tmp_path):
    """With a log file the records go to the root file handler, not back through structlog."""
    configure(log_level="ERROR", log_file=tmp_path / "langflow.log", cache=False)

    Logger(Config())

    for name in GUNICORN_LOGGERS:
        gunicorn_logger = logging.getLogger(name)
        assert gunicorn_logger.handlers == []
        assert gunicorn_logger.propagate is True


def test_gunicorn_error_reaches_the_log_file_exactly_once(tmp_path, monkeypatch):
    """One gunicorn error line lands in the file, at its original size."""
    emitted = []
    original_emit = InterceptHandler.emit
    emit_cap = 8

    def counting_emit(handler_self, record):
        emitted.append(record.name)
        # Hard stop so a regression cannot exhaust CI memory: each lap of the
        # cycle renders the previous lap's payload into the next event.
        if len(emitted) > emit_cap:
            return None
        return original_emit(handler_self, record)

    monkeypatch.setattr(InterceptHandler, "emit", counting_emit)

    log_file = tmp_path / "langflow.log"
    configure(log_level="ERROR", log_file=log_file, cache=False)
    Logger(Config())

    logging.getLogger("gunicorn.error").error("worker timeout")

    for handler in logging.root.handlers:
        handler.flush()

    assert emitted == []
    contents = log_file.read_text()
    assert "worker timeout" in contents
    assert len(contents.splitlines()) == 1
