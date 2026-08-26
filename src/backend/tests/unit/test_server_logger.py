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
UVICORN_LOGGERS = ("uvicorn.error", "uvicorn.access")


@pytest.fixture(autouse=True)
def _restore_logging_state():
    """Put back the process-wide logging state these tests rewire."""
    original_root_handlers = list(logging.root.handlers)
    original_gunicorn_state = {
        name: (list(logging.getLogger(name).handlers), logging.getLogger(name).level, logging.getLogger(name).propagate)
        for name in GUNICORN_LOGGERS + UVICORN_LOGGERS
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


def test_uses_the_root_file_handler_when_a_log_file_is_configured(tmp_path):
    """With a log file the records go to the file handler, not back through structlog."""
    configure(log_level="ERROR", log_file=tmp_path / "langflow.log", cache=False)
    root_handlers = list(logging.root.handlers)

    Logger(Config())

    for name in GUNICORN_LOGGERS:
        gunicorn_logger = logging.getLogger(name)
        assert gunicorn_logger.handlers == root_handlers
        assert not any(isinstance(handler, InterceptHandler) for handler in gunicorn_logger.handlers)
        # UvicornWorker sets propagate = False on its copy, so the handler has to be
        # attached here rather than reached by propagation.
        assert gunicorn_logger.propagate is False


def test_uvicorn_loggers_inherit_a_terminating_handler(tmp_path, monkeypatch):
    """The handlers UvicornWorker copies onto the uvicorn loggers cannot cycle.

    ``UvicornWorker.__init__`` assigns ``gunicorn.error``'s handler list to
    ``uvicorn.error`` and sets ``propagate = False``. An ``InterceptHandler``
    reaching the uvicorn loggers that way is what turned a single uvicorn error
    line into an out-of-memory kill.
    """
    emitted = []
    original_emit = InterceptHandler.emit
    emit_cap = 8

    def counting_emit(handler_self, record):
        emitted.append(record.name)
        if len(emitted) > emit_cap:
            return None
        return original_emit(handler_self, record)

    monkeypatch.setattr(InterceptHandler, "emit", counting_emit)

    log_file = tmp_path / "langflow.log"
    configure(log_level="ERROR", log_file=log_file, cache=False)
    gunicorn_logger = Logger(Config())

    # Exactly what UvicornWorker.__init__ does with the gunicorn logger's handlers.
    for name, source in (("uvicorn.error", gunicorn_logger.error_log), ("uvicorn.access", gunicorn_logger.access_log)):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = source.handlers
        uvicorn_logger.setLevel(source.level)
        uvicorn_logger.propagate = False

    logging.getLogger("uvicorn.error").error("worker failed")

    for handler in logging.getLogger("uvicorn.error").handlers:
        handler.flush()

    assert emitted == []
    contents = log_file.read_text()
    assert "worker failed" in contents
    assert len(contents.splitlines()) == 1


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
