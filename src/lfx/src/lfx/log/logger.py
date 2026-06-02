"""Logging configuration for Langflow using structlog."""

import contextlib
import json
import logging
import logging.handlers
import os
import sys
import warnings
from collections import deque
from datetime import datetime
from pathlib import Path
from threading import Lock, Semaphore
from typing import Any, TypedDict

import orjson
import structlog
from loguru import logger as loguru_logger
from platformdirs import user_cache_dir
from typing_extensions import NotRequired

from lfx.settings import DEV

# OpenTelemetry is optional. Resolve once at import time so the per-record
# processor is a simple attribute check, not a repeated import attempt.
try:
    from opentelemetry import trace as _otel_trace  # type: ignore[import-not-found]
except ImportError:
    _otel_trace = None

VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Map log level names to integers
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class SizedLogBuffer:
    """A buffer for storing log messages for the log retrieval API."""

    def __init__(
        self,
        max_readers: int = 20,  # max number of concurrent readers for the buffer
    ):
        """Initialize the buffer.

        The buffer can be overwritten by an env variable LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE
        because the logger is initialized before the settings_service are loaded.
        """
        self.buffer: deque = deque()

        self._max_readers = max_readers
        self._wlock = Lock()
        self._rsemaphore = Semaphore(max_readers)
        self._max = 0

    def get_write_lock(self) -> Lock:
        """Get the write lock."""
        return self._wlock

    def write(self, message: str) -> None:
        """Write a message to the buffer."""
        record = json.loads(message)
        # ``add_serialized`` stores the rendered text under ``message``; fall back to
        # ``event`` / ``msg`` / ``text`` for records written directly in other shapes.
        log_entry = record.get("message") or record.get("event", record.get("msg", record.get("text", "")))

        # Extract timestamp - support both direct timestamp and nested record.time.timestamp
        timestamp = record.get("timestamp", 0)
        if timestamp == 0 and "record" in record:
            # Support nested structure from tests: record.time.timestamp
            time_info = record["record"].get("time", {})
            timestamp = time_info.get("timestamp", 0)

        if isinstance(timestamp, str):
            # Parse ISO format timestamp
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            epoch = int(dt.timestamp() * 1000)
        else:
            epoch = int(timestamp * 1000)

        with self._wlock:
            if len(self.buffer) >= self.max:
                for _ in range(len(self.buffer) - self.max + 1):
                    self.buffer.popleft()
            self.buffer.append((epoch, log_entry))

    def __len__(self) -> int:
        """Get the length of the buffer."""
        return len(self.buffer)

    def get_after_timestamp(self, timestamp: int, lines: int = 5) -> dict[int, str]:
        """Get log entries after a timestamp."""
        rc = {}

        self._rsemaphore.acquire()
        try:
            with self._wlock:
                for ts, msg in self.buffer:
                    if lines == 0:
                        break
                    if ts >= timestamp and lines > 0:
                        rc[ts] = msg
                        lines -= 1
        finally:
            self._rsemaphore.release()

        return rc

    def get_before_timestamp(self, timestamp: int, lines: int = 5) -> dict[int, str]:
        """Get log entries before a timestamp."""
        self._rsemaphore.acquire()
        try:
            with self._wlock:
                as_list = list(self.buffer)
            max_index = -1
            for i, (ts, _) in enumerate(as_list):
                if ts >= timestamp:
                    max_index = i
                    break
            if max_index == -1:
                return self.get_last_n(lines)
            rc = {}
            start_from = max(max_index - lines, 0)
            for i, (ts, msg) in enumerate(as_list):
                if start_from <= i < max_index:
                    rc[ts] = msg
            return rc
        finally:
            self._rsemaphore.release()

    def get_last_n(self, last_idx: int) -> dict[int, str]:
        """Get the last n log entries."""
        self._rsemaphore.acquire()
        try:
            with self._wlock:
                as_list = list(self.buffer)
            return dict(as_list[-last_idx:])
        finally:
            self._rsemaphore.release()

    @property
    def max(self) -> int:
        """Get the maximum buffer size."""
        # Get it dynamically to allow for env variable changes
        if self._max == 0:
            env_buffer_size = os.getenv("LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE", "0")
            if env_buffer_size.isdigit():
                self._max = int(env_buffer_size)
        return self._max

    @max.setter
    def max(self, value: int) -> None:
        """Set the maximum buffer size."""
        self._max = value

    def enabled(self) -> bool:
        """Check if the buffer is enabled."""
        return self.max > 0

    def max_size(self) -> int:
        """Get the maximum buffer size."""
        return self.max


# log buffer for capturing log messages
log_buffer = SizedLogBuffer()
_file_handler: logging.handlers.RotatingFileHandler | None = None
_loguru_handler_id: int | None = None


def add_serialized(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Add serialized version of the log entry."""
    # Only add serialized if we're in JSON mode (for log buffer)
    if log_buffer.enabled():
        subset = {
            "timestamp": event_dict.get("timestamp", 0),
            "message": event_dict.get("event", ""),
            "level": _method_name.upper(),
            "module": event_dict.get("module", ""),
        }
        event_dict["serialized"] = orjson.dumps(subset)
    return event_dict


def _get_service_info() -> dict[str, str]:
    """Read service metadata once so it can be injected into every log record."""
    service = os.getenv("LANGFLOW_SERVICE_NAME", "langflow")
    version = os.getenv("LANGFLOW_VERSION", "")
    environment = os.getenv("LANGFLOW_ENVIRONMENT", "")
    info = {"service": service}
    if version:
        info["version"] = version
    if environment:
        info["environment"] = environment
    return info


# Default keys whose values are redacted before rendering. Production logs leak
# auth tokens, cookies, and API keys with surprising regularity (third-party
# clients log request bodies, dict reprs, kwargs, etc.); a cheap, default-on
# redactor is the only thing that survives.
DEFAULT_REDACT_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "auth",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
    }
)
_REDACTED = "***"
_REDACT_MAX_DEPTH = 4


def _build_redact_processor(extra_keys: frozenset[str]) -> Any:
    """Build a structlog processor that scrubs sensitive keys.

    Matches case-insensitively, walks nested dicts and lists up to a small
    depth, and replaces values with a fixed sentinel so logs still show the
    shape of the data without leaking the value.
    """
    sensitive = {k.lower() for k in DEFAULT_REDACT_KEYS | extra_keys}

    def _scrub(value: Any, depth: int) -> Any:
        if depth >= _REDACT_MAX_DEPTH:
            return value
        if isinstance(value, dict):
            return {
                k: (_REDACTED if isinstance(k, str) and k.lower() in sensitive else _scrub(v, depth + 1))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [_scrub(item, depth + 1) for item in value]
        if isinstance(value, tuple):
            return tuple(_scrub(item, depth + 1) for item in value)
        return value

    def redact(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        for key in list(event_dict.keys()):
            if isinstance(key, str) and key.lower() in sensitive:
                event_dict[key] = _REDACTED
            else:
                event_dict[key] = _scrub(event_dict[key], 1)
        return event_dict

    return redact


def add_logger_name(logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Attach the bound logger's name as ``logger`` so Grafana can filter on it."""
    name = getattr(logger, "name", None)
    if name:
        event_dict.setdefault("logger", name)
    return event_dict


class _NamedPrintLoggerFactory:
    """Logger factory that preserves the logger name across calls.

    structlog's default ``PrintLoggerFactory`` drops the name passed to
    ``get_logger("x")``. We keep it so the ``add_logger_name`` processor can
    set the ``logger`` field on every record.
    """

    def __init__(self, file: Any) -> None:
        self._file = file

    def __call__(self, *args: Any) -> structlog.PrintLogger:
        logger = structlog.PrintLogger(file=self._file)
        logger.name = args[0] if args else None
        return logger


def add_otel_trace_context(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Inject OpenTelemetry trace_id / span_id when a span is active.

    OpenTelemetry is optional in lfx, so the import is resolved once at module
    load. Runtime calls are wrapped in a broad except: a misbehaving tracer
    SDK must never break logging, which is the only signal an operator has
    when the tracer itself is broken.
    """
    if _otel_trace is None:
        return event_dict
    try:
        ctx = _otel_trace.get_current_span().get_span_context()
    except Exception:  # noqa: BLE001 - logger must never break on a flaky tracer
        return event_dict
    if not ctx.is_valid:
        return event_dict
    event_dict.setdefault("trace_id", format(ctx.trace_id, "032x"))
    event_dict.setdefault("span_id", format(ctx.span_id, "016x"))
    return event_dict


def _apply_logger_level_overrides() -> None:
    """Apply ``LANGFLOW_LOG_LEVELS`` env var: ``name=LEVEL,name=LEVEL,...``.

    Used to quiet noisy third-party loggers (``sqlalchemy.engine``, ``httpx``,
    ``httpcore``, ``urllib3``) in production without changing global defaults.

    Malformed entries (missing ``=``, unknown level, empty name) raise a
    warning instead of being silently dropped so operators see typos like
    ``WARN`` instead of ``WARNING``.
    """
    raw = os.getenv("LANGFLOW_LOG_LEVELS", "").strip()
    if not raw:
        return
    for pair in raw.split(","):
        entry = pair.strip()
        if not entry:
            continue
        if "=" not in entry:
            warnings.warn(
                f"LANGFLOW_LOG_LEVELS: ignoring {entry!r} (expected 'name=LEVEL')",
                stacklevel=2,
            )
            continue
        name, _, level = entry.partition("=")
        name = name.strip()
        level_str = level.strip().upper()
        if not name:
            warnings.warn(
                f"LANGFLOW_LOG_LEVELS: ignoring {entry!r} (empty logger name)",
                stacklevel=2,
            )
            continue
        numeric = LOG_LEVEL_MAP.get(level_str)
        if numeric is None:
            warnings.warn(
                f"LANGFLOW_LOG_LEVELS: ignoring {entry!r} (unknown level {level_str!r}, "
                f"expected one of {sorted(LOG_LEVEL_MAP)})",
                stacklevel=2,
            )
            continue
        logging.getLogger(name).setLevel(numeric)


def buffer_writer(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Write to log buffer if enabled."""
    if log_buffer.enabled() and "serialized" in event_dict:
        # Use the already-serialized version prepared by add_serialized()
        # This avoids duplicate serialization and ensures consistency
        serialized_bytes = event_dict["serialized"]
        log_buffer.write(serialized_bytes.decode("utf-8"))
    return event_dict


def _forward_loguru_message(message) -> None:
    """Forward Loguru messages through Langflow's configured structlog pipeline."""
    record = message.record
    structlog_logger = structlog.get_logger(record["name"])
    level_name = record["level"].name.lower()
    log_method = getattr(structlog_logger, level_name, structlog_logger.info)
    if record["exception"]:
        log_method(record["message"], exc_info=record["exception"])
    else:
        log_method(record["message"])


def setup_loguru_logger(log_level: str, *, enqueue: bool = False) -> None:
    """Route Loguru's default logger through Langflow logging."""
    global _loguru_handler_id  # noqa: PLW0603

    if _loguru_handler_id is not None:
        with contextlib.suppress(ValueError):
            loguru_logger.remove(_loguru_handler_id)
    else:
        with contextlib.suppress(ValueError):
            loguru_logger.remove(0)

    _loguru_handler_id = loguru_logger.add(
        _forward_loguru_message,
        level=log_level.upper(),
        enqueue=enqueue,
        format="{message}",
    )


def setup_log_file(log_file: Path, *, max_bytes: int, formatter: logging.Formatter | None = None) -> None:
    """Set up Langflow's rotating file handler.

    ``formatter`` lets JSON modes attach a ``structlog.stdlib.ProcessorFormatter``
    so third-party stdlib records (uvicorn, sqlalchemy, httpx, ...) are rendered
    as JSON through the same processor chain as application logs. When omitted,
    the handler writes the message verbatim (structlog has already rendered it).
    """
    global _file_handler  # noqa: PLW0603

    if _file_handler is not None:
        logging.root.removeHandler(_file_handler)
        _file_handler.close()

    _file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=5,
    )
    _file_handler.setFormatter(formatter if formatter is not None else logging.Formatter("%(message)s"))
    logging.root.addHandler(_file_handler)


class LogConfig(TypedDict):
    """Configuration for logging."""

    log_level: NotRequired[str]
    log_file: NotRequired[Path]
    disable: NotRequired[bool]
    log_env: NotRequired[str]
    log_format: NotRequired[str]


def configure(
    *,
    log_level: str | None = None,
    log_file: Path | None = None,
    disable: bool | None = False,
    log_env: str | None = None,
    log_format: str | None = None,
    log_rotation: str | None = None,
    cache: bool | None = None,
    output_file=None,
) -> None:
    """Configure the logger."""
    # Resolve every effective input (env-var fallbacks + level validation) up
    # front so the early-return below can compare a fingerprint of the *entire*
    # resulting configuration, not just the log level. The old check compared
    # only the resolved level, so a second call that changed
    # log_env / log_file / log_format / output_file / disable at the same level
    # silently no-opped -- skipping the file handler and renderer switch. That
    # was both a real footgun and a source of test-isolation flakiness (a prior
    # same-level configure() made a later file-mode configure() do nothing,
    # surfacing as FileNotFoundError when a test read the log file).
    if log_level is None and os.getenv("LANGFLOW_LOG_LEVEL", "").upper() in VALID_LOG_LEVELS:
        log_level = os.getenv("LANGFLOW_LOG_LEVEL")
    if log_level is None or log_level.upper() not in LOG_LEVEL_MAP:
        log_level = "ERROR"

    if log_file is None:
        env_log_file = os.getenv("LANGFLOW_LOG_FILE", "")
        log_file = Path(env_log_file) if env_log_file else None

    if log_env is None:
        log_env = os.getenv("LANGFLOW_LOG_ENV", "")

    # Get log format from env if not provided
    if log_format is None:
        log_format = os.getenv("LANGFLOW_LOG_FORMAT")

    numeric_level = LOG_LEVEL_MAP.get(log_level.upper(), logging.ERROR)

    # Fingerprint of every caller-supplied input that changes the resulting
    # setup. Stored on the wrapper_class (below) so structlog.reset_defaults()
    # -- used between tests -- invalidates it automatically and the next call
    # rebuilds from scratch. Env-only toggles (e.g. LANGFLOW_PRETTY_LOGS) are not
    # part of the fingerprint: the four env-backed args above are already folded
    # into their resolved values, and the remainder are process-stable.
    config_fingerprint = (
        numeric_level,
        log_env,
        str(log_file) if log_file is not None else None,
        log_format,
        bool(disable),
        log_rotation,
        cache if cache is not None else True,
        output_file,
    )
    cfg = structlog.get_config() if structlog.is_configured() else {}
    if getattr(cfg.get("wrapper_class"), "config_fingerprint", None) == config_fingerprint:
        return

    # Configure processors based on environment
    service_info = _get_service_info()

    def _add_service_info(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        for key, value in service_info.items():
            event_dict.setdefault(key, value)
        return event_dict

    extra_redact = frozenset(
        k.strip().lower() for k in os.getenv("LANGFLOW_LOG_REDACT_KEYS", "").split(",") if k.strip()
    )
    redact_processor = _build_redact_processor(extra_redact)

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        add_logger_name,
        add_otel_trace_context,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_service_info,
    ]

    # Add callsite information only when LANGFLOW_DEV is set
    if DEV:
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            )
        )

    processors.extend(
        [
            redact_processor,
            add_serialized,
            buffer_writer,
        ]
    )

    # Configure output based on environment.
    # For machine-parseable renderers, serialize exc_info as structured tracebacks
    # so Grafana/Loki see a complete stack trace (type, value, frames) instead of
    # dropping the exception or rendering its repr. ConsoleRenderer formats
    # exc_info itself, so we don't add a tracebacks processor on that path.
    #
    # `show_locals` is OFF by default in JSON output because frame locals can
    # leak secrets (API keys, env, request bodies). Opt in with
    # LANGFLOW_LOG_TRACE_LOCALS=true when you need it for local debugging.
    show_locals = os.getenv("LANGFLOW_LOG_TRACE_LOCALS", "false").lower() == "true"
    json_traceback = structlog.processors.ExceptionRenderer(
        structlog.tracebacks.ExceptionDictTransformer(show_locals=show_locals, max_frames=50)
    )

    # When JSON output is written to a file, render through a stdlib
    # ProcessorFormatter on the rotating handler instead of an inline
    # JSONRenderer. That routes foreign stdlib records (uvicorn, sqlalchemy,
    # httpx, asyncio) through the same renderer and the same redaction, so the
    # file is a single JSON stream and PII redaction is not bypassed -- while the
    # stdlib RotatingFileHandler keeps log rotation. Foreign records are enriched
    # by ``foreign_pre_chain``; structlog records carry the context built above
    # and are handed off via ``wrap_for_formatter``.
    file_json_formatter: logging.Formatter | None = None

    def _append_json_tail() -> None:
        nonlocal file_json_formatter
        if log_file:
            processors.append(structlog.stdlib.ProcessorFormatter.wrap_for_formatter)
            foreign_pre_chain = [
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.ExtraAdder(),
                # NB: not ``structlog.stdlib.add_log_level`` -- that trusts
                # ``record.levelname``, which a third-party ``addLevelName`` call
                # can corrupt. Derive from the numeric level instead.
                add_stdlib_log_level_from_record,
                structlog.stdlib.add_logger_name,
                add_otel_trace_context,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                _add_service_info,
                redact_processor,
            ]
            file_json_formatter = structlog.stdlib.ProcessorFormatter(
                foreign_pre_chain=foreign_pre_chain,
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    json_traceback,
                    structlog.processors.JSONRenderer(),
                ],
            )
        else:
            processors.append(json_traceback)
            processors.append(structlog.processors.JSONRenderer())

    if log_env.lower() in ("container", "container_json"):
        _append_json_tail()
    elif log_env.lower() == "container_csv":
        processors.append(structlog.processors.format_exc_info)
        # Include callsite fields in key order when DEV is enabled
        key_order = ["timestamp", "level", "event"]
        if DEV:
            key_order += ["filename", "func_name", "lineno"]

        processors.append(structlog.processors.KeyValueRenderer(key_order=key_order, drop_missing=True))
    else:
        # Use rich console for pretty printing based on environment variable
        log_stdout_pretty = os.getenv("LANGFLOW_PRETTY_LOGS", "true").lower() == "true"
        if log_stdout_pretty:
            # If custom format is provided, use KeyValueRenderer with custom format
            if log_format:
                processors.append(structlog.processors.format_exc_info)
                processors.append(structlog.processors.KeyValueRenderer())
            else:
                processors.append(structlog.dev.ConsoleRenderer(colors=True))
        else:
            _append_json_tail()

    # Create the filtering wrapper. ``numeric_level`` was resolved above for the
    # fingerprint. Attach min_level (kept for back-compat) and the full config
    # fingerprint so the next configure() call early-returns only when every
    # effective input is unchanged.
    wrapper_class = structlog.make_filtering_bound_logger(numeric_level)
    wrapper_class.min_level = numeric_level
    wrapper_class.config_fingerprint = config_fingerprint

    # Configure structlog
    # Default to stdout for backward compatibility, unless output_file is specified
    log_output_file = output_file if output_file is not None else sys.stdout

    # Wipe cached loggers before reconfiguring so any module that captured a
    # logger before the real configure() call picks up the new processor chain
    # (otherwise cache_logger_on_first_use=True binds the bootstrap chain
    # permanently to that reference).
    structlog.reset_defaults()

    structlog.configure(
        processors=processors,
        wrapper_class=wrapper_class,
        context_class=dict,
        logger_factory=_NamedPrintLoggerFactory(file=log_output_file)
        if not log_file
        else structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=cache if cache is not None else True,
    )

    # Set up file logging if needed
    if log_file:
        if not log_file.parent.exists():
            cache_dir = Path(user_cache_dir("langflow"))
            log_file = cache_dir / "langflow.log"

        # Parse rotation settings
        if log_rotation:
            # Handle rotation like "1 day", "100 MB", etc.
            max_bytes = 10 * 1024 * 1024  # Default 10MB
            if "MB" in log_rotation.upper():
                try:
                    # Look for pattern like "100 MB" (with space)
                    parts = log_rotation.split()
                    expected_parts = 2
                    if len(parts) >= expected_parts and parts[1].upper() == "MB":
                        mb = int(parts[0])
                        if mb > 0:  # Only use valid positive values
                            max_bytes = mb * 1024 * 1024
                except (ValueError, IndexError):
                    pass
        else:
            max_bytes = 10 * 1024 * 1024  # Default 10MB

        # Since structlog doesn't have built-in rotation, we'll use stdlib logging for file output.
        # In JSON file mode the formatter renders both structlog and foreign stdlib records as JSON.
        setup_log_file(log_file, max_bytes=max_bytes, formatter=file_json_formatter)
        logging.root.setLevel(numeric_level)

    # Set up interceptors for uvicorn and gunicorn
    setup_uvicorn_logger()
    setup_gunicorn_logger()

    # In JSON modes we want a single unified stdout stream: every stdlib log
    # record (uvicorn access logs, sqlalchemy, httpx, langchain, asyncio)
    # routed into structlog so it comes out as JSON instead of unstructured
    # text. In non-JSON modes leave stdlib alone so dev console output stays
    # readable.
    json_mode = log_env.lower() in ("container", "container_json") or (
        not log_env and os.getenv("LANGFLOW_PRETTY_LOGS", "true").lower() != "true"
    )
    if json_mode and not log_file:
        _install_stdlib_intercept(numeric_level)

    # Apply per-logger level overrides last so user env beats library defaults.
    _apply_logger_level_overrides()

    # Create the global logger instance
    global logger  # noqa: PLW0603
    logger = structlog.get_logger()
    setup_loguru_logger(log_level)

    if disable:
        # In structlog, we can set a very high filter level to effectively disable logging
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        )

    logger.debug("Logger set up with log level: %s", log_level)


def setup_uvicorn_logger() -> None:
    """Redirect uvicorn logs through structlog."""
    loggers = (logging.getLogger(name) for name in logging.root.manager.loggerDict if name.startswith("uvicorn."))
    for uvicorn_logger in loggers:
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True


def setup_gunicorn_logger() -> None:
    """Redirect gunicorn logs through structlog."""
    logging.getLogger("gunicorn.error").handlers = []
    logging.getLogger("gunicorn.error").propagate = True
    logging.getLogger("gunicorn.access").handlers = []
    logging.getLogger("gunicorn.access").propagate = True


_STDLIB_LEVEL_TO_STRUCTLOG = (
    (logging.CRITICAL, "critical"),
    (logging.ERROR, "error"),
    (logging.WARNING, "warning"),
    (logging.INFO, "info"),
)


def _levelno_to_structlog_name(levelno: int) -> str:
    """Map a stdlib numeric level to a lowercase structlog level name.

    Derives the name from the immutable ``levelno`` instead of ``levelname``
    because third-party libraries can rewrite stdlib level names via
    ``logging.addLevelName`` (e.g. ``ibm_watsonx_orchestrate`` wraps them in ANSI
    color codes). ``levelno`` is never mutated, so the rendered ``level`` field
    stays clean and filterable.
    """
    for threshold, name in _STDLIB_LEVEL_TO_STRUCTLOG:
        if levelno >= threshold:
            return name
    return "debug"


def add_stdlib_log_level_from_record(_logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Set ``level`` from a foreign ``LogRecord``'s numeric level.

    Drop-in replacement for ``structlog.stdlib.add_log_level`` on the
    ProcessorFormatter ``foreign_pre_chain``. structlog derives a foreign
    record's level from ``record.levelname.lower()``; when a third-party library
    has rewritten that name via ``logging.addLevelName`` (e.g. wrapping it in
    ANSI color codes), the mangled string would otherwise land verbatim in the
    JSON ``level`` field and break level-based filtering in Grafana/Loki.
    Deriving from the immutable ``levelno`` keeps the field stable. Mirrors the
    numeric-level logic the stdout-mode ``InterceptHandler`` already uses.
    """
    record = event_dict.get("_record")
    levelno = getattr(record, "levelno", None)
    if levelno is None:
        # No stdlib record on the chain (not expected on the foreign path):
        # fall back to the method name structlog computed.
        event_dict.setdefault("level", method_name)
    else:
        event_dict["level"] = _levelno_to_structlog_name(levelno)
    return event_dict


# Attributes present on a vanilla LogRecord. Anything else in record.__dict__ was
# attached via ``logging.*(..., extra={...})`` and is forwarded to structlog so it
# lands as a structured field (and is therefore subject to PII redaction), mirroring
# the ExtraAdder used on the file-mode ProcessorFormatter path.
_RESERVED_LOGRECORD_ATTRS = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class InterceptHandler(logging.Handler):
    """Route stdlib logging records into structlog.

    Forwards ``exc_info`` and ``stack_info`` so library tracebacks (httpx,
    sqlalchemy, langchain, uvicorn) survive into the JSON output. Without
    this, errors raised inside third-party libraries log a one-line message
    with no stack trace.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Mirrors the stdlib Handler.emit safety net: a malformed third-party
        # log call (e.g. mismatched %-format args) must not propagate up and
        # crash the request path. Anything that raises here is routed to
        # handleError, which is the documented contract callers expect.
        try:
            structlog_logger = structlog.get_logger(record.name)
            kwargs: dict[str, Any] = {}
            if record.exc_info:
                kwargs["exc_info"] = record.exc_info
            if record.stack_info:
                # stdlib already formats stack_info as a string. Pass it as
                # the rendered ``stack`` field directly so it survives without
                # needing StackInfoRenderer to recompute from a different frame.
                kwargs["stack"] = record.stack_info
            for key, value in record.__dict__.items():
                if key not in _RESERVED_LOGRECORD_ATTRS and not key.startswith("_") and key not in kwargs:
                    kwargs[key] = value
            method_name = _levelno_to_structlog_name(record.levelno)
            getattr(structlog_logger, method_name)(record.getMessage(), **kwargs)
        except Exception:  # noqa: BLE001 - logging must never break the caller
            self.handleError(record)


def _install_stdlib_intercept(numeric_level: int) -> None:
    """Install (or refresh) the InterceptHandler on the stdlib root logger.

    Routes every stdlib log record (uvicorn, sqlalchemy, httpx, langchain,
    asyncio, ...) into structlog so the entire process emits a single JSON
    stream. Re-runnable: a second call updates the level rather than stacking
    handlers.
    """
    root = logging.root
    handler = next((h for h in root.handlers if isinstance(h, InterceptHandler)), None)
    if handler is None:
        handler = InterceptHandler()
        root.addHandler(handler)
    handler.setLevel(numeric_level)
    root.setLevel(numeric_level)


# Initialize logger - will be reconfigured when configure() is called
# Set it to critical level
logger: structlog.BoundLogger = structlog.get_logger()
configure(log_level="CRITICAL", cache=False)
