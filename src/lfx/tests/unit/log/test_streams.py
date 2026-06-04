"""Regression tests for stdout/stderr encoding resilience on Windows consoles."""

import importlib
import io

import structlog
from lfx.log._streams import make_streams_resilient


def _cp1252_stream() -> tuple[io.TextIOWrapper, io.BytesIO]:
    """A text stream that behaves like a strict Windows cp1252 console."""
    raw = io.BytesIO()
    return io.TextIOWrapper(raw, encoding="cp1252"), raw


def test_make_streams_resilient_sets_backslashreplace(monkeypatch):
    out, _ = _cp1252_stream()
    err, _ = _cp1252_stream()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)

    make_streams_resilient()

    assert out.errors == "backslashreplace"
    assert err.errors == "backslashreplace"


def test_logging_exception_to_cp1252_stdout_does_not_crash(monkeypatch):
    """A logged traceback must never raise UnicodeEncodeError on a cp1252 console.

    structlog's ConsoleRenderer emits box-drawing glyphs that cp1252 cannot
    encode; without the resilience shim the encode error is raised inside the
    logging call, masking the original error and aborting the request.
    """
    stream, raw = _cp1252_stream()
    monkeypatch.setattr("sys.stdout", stream)

    make_streams_resilient()

    logmod = importlib.import_module("lfx.log.logger")
    logmod.configure(log_level="ERROR", cache=False)
    log = structlog.get_logger("test")

    msg = "THIS IS A TEST ERROR MESSAGE"
    try:
        raise ValueError(msg)
    except ValueError:
        log.exception("boom")

    stream.flush()
    rendered = raw.getvalue().decode("cp1252", errors="replace")
    assert "THIS IS A TEST ERROR MESSAGE" in rendered


def test_reconfigure_is_safe_when_stream_is_none(monkeypatch):
    monkeypatch.setattr("sys.stdout", None)
    monkeypatch.setattr("sys.stderr", None)
    monkeypatch.setattr("sys.__stdout__", None)
    monkeypatch.setattr("sys.__stderr__", None)

    make_streams_resilient()
