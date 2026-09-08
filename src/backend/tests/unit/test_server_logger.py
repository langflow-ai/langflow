"""Tests for the gunicorn logging wiring in ``langflow.server``.

``Logger`` used to attach an ``InterceptHandler`` to ``gunicorn.error`` and
``gunicorn.access`` unconditionally. With a log file configured, structlog
resolves those names back to the same stdlib loggers, so every intercepted
record was handed straight back to the handler that intercepted it.
"""

import contextlib
import importlib
import logging
import logging.handlers

import pytest
import structlog
from gunicorn.config import Config
from langflow.server import Logger
from lfx.log.logger import InterceptHandler, configure

GUNICORN_LOGGERS = ("gunicorn.error", "gunicorn.access")
UVICORN_LOGGERS = ("uvicorn.error", "uvicorn.access")


@pytest.fixture(autouse=True)
def _restore_logging_state():
    """Put back the process-wide logging state these tests rewire.

    ``configure(log_file=...)`` adds a ``RotatingFileHandler`` to the root logger,
    raises the root level and parks the handler in ``lfx.log.logger._file_handler``.
    Left behind, that handler holds an open file inside a since-deleted tmp_path and
    whatever test the xdist worker picks up next logs into it. Mirrors the module
    fixture in ``test_logger.py``.
    """
    # ``import lfx.log.logger as ...`` would bind the logger object ``lfx.log``
    # re-exports under that name, not the module.
    lfx_log = importlib.import_module("lfx.log.logger")

    orig_structlog_config = dict(structlog.get_config())
    orig_root_handlers = logging.root.handlers[:]
    orig_root_level = logging.root.level
    orig_file_handler = lfx_log._file_handler
    orig_logger_state = {
        name: (logging.getLogger(name).handlers[:], logging.getLogger(name).level, logging.getLogger(name).propagate)
        for name in GUNICORN_LOGGERS + UVICORN_LOGGERS
    }

    try:
        yield
    finally:
        structlog.configure(**orig_structlog_config)

        # Drop handlers these tests added, closing file handlers so they stop
        # pointing into deleted temp dirs. If configure() replaced the lfx-managed
        # file handler, setup_log_file() already closed the original, so it must
        # not be reinstalled.
        for handler in logging.root.handlers[:]:
            if handler not in orig_root_handlers:
                logging.root.removeHandler(handler)
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    with contextlib.suppress(OSError, ValueError):
                        handler.close()
        restored_handlers = orig_root_handlers
        if lfx_log._file_handler is not orig_file_handler:
            restored_handlers = [h for h in orig_root_handlers if h is not orig_file_handler]
            lfx_log._file_handler = None
        logging.root.handlers[:] = restored_handlers
        logging.root.setLevel(orig_root_level)

        for name, (handlers, level, propagate) in orig_logger_state.items():
            named_logger = logging.getLogger(name)
            named_logger.handlers = handlers
            named_logger.setLevel(level)
            named_logger.propagate = propagate


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
        """Record every interception and cap the laps a regression could run."""
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
        """Record every interception and cap the laps a regression could run."""
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
