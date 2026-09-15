"""Tests for ``langflow.server.Logger``'s stdlib logging wiring.

Regression cover for LE-2454 / #14776: with ``LANGFLOW_LOG_FILE`` set, the
gunicorn loggers used to be given an ``InterceptHandler`` unconditionally. In that
mode ``structlog.get_logger(name)`` resolves back to the stdlib logger of the same
name, so the handler fed the logger it was attached to and the record cycled,
growing every lap until the process was OOM-killed.

Three things have to hold, and each is easy to break independently:

* stdout mode keeps the intercept (unchanged behaviour);
* file mode attaches the rotating file handler *itself*, not an empty list --
  ``UvicornWorker`` copies this list onto the uvicorn loggers and sets
  ``propagate = False``, so an empty list silently drops every uvicorn record;
* it must hold when ``configure()`` already ran before the ``Logger`` is built,
  because the repeat call early-returns on an unchanged fingerprint and never
  re-runs ``setup_gunicorn_logger()``.
"""

import contextlib
import importlib
import logging
from pathlib import Path

import pytest
import structlog
from gunicorn.config import Config
from langflow.server import Logger
from lfx.log.logger import InterceptHandler, configure, get_file_handler

# A cycle regression would recurse until the machine gives out. Cap the number of
# times ``InterceptHandler.emit`` may run per test so a regression fails an assert
# in milliseconds instead of exhausting CI memory.
EMIT_CAP = 20

GUNICORN_LOGGERS = ("gunicorn.error", "gunicorn.access")
UVICORN_LOGGERS = ("uvicorn.error", "uvicorn.access")


@pytest.fixture(autouse=True)
def _restore_logging_state():
    """Snapshot and restore every process-global this module rewires.

    ``configure(log_file=...)`` sets ``logging.root``'s level, installs a
    ``RotatingFileHandler`` on the root logger and stores it in the
    ``lfx.log.logger._file_handler`` module global. ``Logger.__init__`` then edits
    the gunicorn loggers, and the uvicorn tests edit theirs. None of that is
    undone automatically, and leaking a handler pointed at a deleted tmp_path into
    a later test is how this module would poison an xdist worker.
    """
    lfx_log = importlib.import_module("lfx.log.logger")

    orig_structlog_config = dict(structlog.get_config())
    orig_root_handlers = logging.root.handlers[:]
    orig_root_level = logging.root.level
    orig_file_handler = lfx_log._file_handler
    orig_named = {
        name: (lg.handlers[:], lg.level, lg.propagate)
        for name in (*GUNICORN_LOGGERS, *UVICORN_LOGGERS)
        if (lg := logging.getLogger(name))
    }

    yield

    # Close any file handler this test opened before putting the old one back,
    # otherwise the fd leaks and the tmp_path cannot be cleaned up on Windows.
    for handler in logging.root.handlers[:]:
        if handler not in orig_root_handlers:
            logging.root.removeHandler(handler)
            with contextlib.suppress(OSError, ValueError):
                handler.close()

    # If configure() replaced the lfx-managed file handler it also *closed* the
    # original, so reinstalling that one would put a handler pointed at a
    # torn-down tmp_path back on the root logger -- where the next record silently
    # re-creates the file or fails into handleError. Drop it instead, exactly as
    # the module fixture in test_logger.py does.
    restored_handlers = orig_root_handlers
    if lfx_log._file_handler is not orig_file_handler:
        restored_handlers = [h for h in orig_root_handlers if h is not orig_file_handler]
        lfx_log._file_handler = None
    else:
        lfx_log._file_handler = orig_file_handler

    logging.root.handlers[:] = restored_handlers
    logging.root.setLevel(orig_root_level)
    for name, (handlers, level, propagate) in orig_named.items():
        lg = logging.getLogger(name)
        lg.handlers[:] = handlers
        lg.setLevel(level)
        lg.propagate = propagate

    structlog.configure(**orig_structlog_config)


@pytest.fixture
def capped_emit(monkeypatch):
    """Count ``InterceptHandler.emit`` calls and abort past ``EMIT_CAP``."""
    calls = []
    original = InterceptHandler.emit

    def counting_emit(self, record):
        calls.append(record)
        if len(calls) > EMIT_CAP:
            msg = f"InterceptHandler.emit re-entered more than {EMIT_CAP} times -- the LE-2454 cycle is back"
            raise AssertionError(msg)
        return original(self, record)

    monkeypatch.setattr(InterceptHandler, "emit", counting_emit)
    return calls


def _gunicorn_config() -> Config:
    cfg = Config()
    cfg.set("loglevel", "info")
    return cfg


def _read_log(log_file: Path) -> list[str]:
    handler = get_file_handler()
    if handler is not None:
        handler.flush()
    if not log_file.exists():
        return []
    return [line for line in log_file.read_text().splitlines() if line]


class TestHandlerWiring:
    """Which handler each mode installs on the gunicorn loggers."""

    def test_stdout_mode_keeps_the_intercept_handler(self):
        """With no log file structlog renders directly, so the intercept terminates."""
        configure(log_level="ERROR")

        Logger(_gunicorn_config())

        for name in GUNICORN_LOGGERS:
            handlers = logging.getLogger(name).handlers
            assert len(handlers) == 1
            assert isinstance(handlers[0], InterceptHandler)

    def test_file_mode_attaches_the_file_handler_instead(self, tmp_path):
        """In file mode an intercept would cycle, so the file handler is attached directly."""
        configure(log_level="ERROR", log_file=tmp_path / "langflow.log")

        Logger(_gunicorn_config())

        for name in GUNICORN_LOGGERS:
            lg = logging.getLogger(name)
            assert not any(isinstance(h, InterceptHandler) for h in lg.handlers)
            assert lg.handlers == [get_file_handler()]
            # The handler is attached directly; propagating to root -- which owns
            # that same handler -- would write every record twice.
            assert lg.propagate is False


class TestRecordsReachTheFile:
    """One record in, one line out, in the modes that used to lose or loop it."""

    def test_gunicorn_error_is_written_exactly_once(self, tmp_path, capped_emit):
        log_file = tmp_path / "langflow.log"
        configure(log_level="ERROR", log_file=log_file)
        Logger(_gunicorn_config())

        logging.getLogger("gunicorn.error").error("boom")

        assert _read_log(log_file) == ["boom"]
        assert capped_emit == []

    def test_uvicorn_logger_inherits_a_terminating_handler(self, tmp_path, capped_emit):
        """Replicates ``UvicornWorker.__init__``'s handler copy.

        uvicorn assigns gunicorn's handler *list* to the uvicorn loggers and turns
        propagation off, so whatever ``Logger`` installed is the only thing standing
        between a uvicorn record and the void.
        """
        log_file = tmp_path / "langflow.log"
        configure(log_level="ERROR", log_file=log_file)
        Logger(_gunicorn_config())

        for gunicorn_name, uvicorn_name in zip(GUNICORN_LOGGERS, UVICORN_LOGGERS, strict=True):
            uvicorn_logger = logging.getLogger(uvicorn_name)
            uvicorn_logger.handlers = logging.getLogger(gunicorn_name).handlers
            uvicorn_logger.setLevel(logging.WARNING)
            uvicorn_logger.propagate = False

        logging.getLogger("uvicorn.error").error("boom")

        assert _read_log(log_file) == ["boom"]
        assert capped_emit == []

    def test_holds_when_configure_early_returns(self, tmp_path, capped_emit):
        """LE-2454's deciding variable: ``configure()`` ran before the ``Logger``.

        This is the real boot order -- ``langflow/__main__.py`` configures logging
        long before ``LangflowApplication`` is constructed. The app's later
        ``configure()`` call carries identical arguments, so it early-returns on the
        unchanged fingerprint and never reaches ``setup_gunicorn_logger()``. Nothing
        cleans up after ``Logger.__init__``, which is why the fix cannot rely on it.
        """
        log_file = tmp_path / "langflow.log"
        configure(log_level="ERROR", log_file=log_file)
        Logger(_gunicorn_config())

        # Same arguments -> unchanged fingerprint -> early return.
        configure(log_level="ERROR", log_file=log_file)

        assert not any(isinstance(h, InterceptHandler) for h in logging.getLogger("gunicorn.error").handlers)

        logging.getLogger("gunicorn.error").error("boom")

        assert _read_log(log_file) == ["boom"]
        assert capped_emit == []

    def test_large_record_is_not_amplified(self, tmp_path, capped_emit):
        """Pretty mode's failure was a threshold, not an absence.

        Each lap of the cycle carried a copy of the previous message, so peak memory
        and bytes-on-disk scaled with the size of the originating record: a 4-byte
        message survived while a 10 MB one OOM-killed the process. A short-message
        test therefore passes against the unfixed code -- this one has to be big.
        """
        log_file = tmp_path / "langflow.log"
        configure(log_level="ERROR", log_file=log_file)
        Logger(_gunicorn_config())

        payload = "x" * 1_000_000
        logging.getLogger("gunicorn.error").error(payload)

        lines = _read_log(log_file)
        assert lines == [payload]
        # Written once, not once per lap.
        assert log_file.stat().st_size < 2 * len(payload)
        assert capped_emit == []
