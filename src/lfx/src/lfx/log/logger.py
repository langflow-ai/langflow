"""Logging configuration for Langflow using structlog."""

import contextlib
import json
import logging
import logging.handlers
import os
import sys
import warnings
from collections import deque
from collections.abc import Iterator
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

try:
    from opentelemetry import _logs as _otel_logs  # type: ignore[import-not-found]
    from opentelemetry._logs import SeverityNumber as _OtelSeverity  # type: ignore[import-not-found]
except ImportError:
    _otel_logs = None
    _OtelSeverity = None

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


_OTEL_LOG_SEVERITY = {
    "debug": 5,  # SeverityNumber.DEBUG
    "info": 9,  # INFO
    "warning": 13,  # WARN
    "warn": 13,
    "error": 17,  # ERROR
    "critical": 21,  # FATAL
    "exception": 17,
}

# Structured keys that describe the record itself rather than the event. They become
# first-class LogRecord fields or are already covered by the resource, so re-sending them as
# attributes would just duplicate bytes on every line.
#
# ``exc_info`` is here for a different reason: it is a leak, not a duplicate. This processor runs
# before ``ExceptionRenderer`` (which is what turns exc_info into a structured traceback), so at
# this point the value is still a raw ``(type, value, traceback)`` tuple and ``str()`` of it
# embeds the exception's *message* -- the text every call site below is careful to keep out of
# the body. It exported that way from every ``logger.exception`` call in the codebase without any
# individual call site being at fault. Dropped unconditionally, in both body policies, and
# replaced by the derived ``error.type`` / ``error.chain`` attributes, which carry the class
# names an operator actually pivots on.
_OTEL_LOG_SKIP_KEYS = frozenset({"event", "level", "timestamp", "trace_id", "span_id", "exc_info"})

# Do not ship DEBUG to the operator's backend by default.
#
# The console is the developer's, the APM is the operator's, and they are not the same trust
# boundary. Langflow's DEBUG output includes flow payloads (graph/base.py logs "Run outputs:"
# with the rendered outputs), and the redaction processor only scrubs known sensitive *keys*,
# not free text inside a message. INFO is the floor because it drops that bulk payload logging.
#
# On its own a severity threshold does NOT make the channel content-free, which is why the
# scope allowlist below exists as well. Flow-derived text reaches ERROR routinely: an agent's
# ExceptionWithMessageError interpolates the model's partial completion into its own str(), and
# a SQLAlchemy StatementError carries the bound parameters -- the chat text -- in its message.
# Severity decides *whether* a record is exported; the body policy decides whether its text is.
#
# An operator who needs DEBUG in their backend can lower it deliberately.
_OTEL_MIN_LOG_SEVERITY_DEFAULT = "INFO"


_INFO_SEVERITY = _OTEL_LOG_SEVERITY["info"]
_otel_min_severity_cache: int | None = None


def _otel_min_severity() -> int:
    """Resolve the export floor once, and say so out loud when it is lowered past INFO.

    Resolved once rather than per record: this runs on every log line, and the answer cannot
    change without a restart anyway.

    Lowering it is allowed on purpose -- an operator debugging a live incident may genuinely
    need DEBUG in their backend, and refusing outright would just get worked around. But it
    is the one setting that starts sending flow payloads to a third party, and the person who
    sets it in a Helm chart is often not the person who knows that, so it must never happen
    quietly. Unknown values fall back to INFO rather than off, so a typo cannot silently open
    it.
    """
    global _otel_min_severity_cache  # noqa: PLW0603
    if _otel_min_severity_cache is not None:
        return _otel_min_severity_cache

    raw = os.getenv("LANGFLOW_OTEL_LOG_LEVEL", _OTEL_MIN_LOG_SEVERITY_DEFAULT).strip()
    severity = _OTEL_LOG_SEVERITY.get(raw.lower())
    # Cache before warning, not after: this is called from inside a log processor, and if
    # warnings are routed into logging (logging.captureWarnings) the warning re-enters here.
    # With the cache already set that re-entry returns immediately instead of recursing.
    _otel_min_severity_cache = severity if severity is not None else _INFO_SEVERITY
    # The notice is best-effort, and deliberately cannot fail the caller. warnings.warn raises
    # when warnings are escalated to errors (-W error, or filterwarnings("error") in a test or
    # CI config), and this is reached from inside a structlog processor on the first record it
    # handles. Letting that propagate would take out logging itself, which is a far worse
    # outcome than a missing notice -- and the floor is already resolved and cached above, so
    # the export behaviour is correct either way.
    with contextlib.suppress(Exception):
        if severity is None:
            warnings.warn(
                f"LANGFLOW_OTEL_LOG_LEVEL: ignoring {raw!r} (expected one of "
                f"{sorted(_OTEL_LOG_SEVERITY)}); exporting {_OTEL_MIN_LOG_SEVERITY_DEFAULT} and above.",
                stacklevel=2,
            )
        elif severity < _INFO_SEVERITY:
            warnings.warn(
                f"LANGFLOW_OTEL_LOG_LEVEL={raw!r} exports DEBUG log records to the configured OTLP "
                "endpoint. Langflow logs flow inputs and outputs at DEBUG. Their bodies are "
                "withheld unless LANGFLOW_OTEL_LOG_BODIES=all is also set, so this alone raises "
                "the volume rather than the content; with both set, prompt and completion "
                "content will reach that backend. Use INFO unless that is intended.",
                stacklevel=2,
            )
    return _otel_min_severity_cache


# The scope name operator statements are grouped under in the APM. Cosmetic: it makes them easy
# to filter on, and it mirrors APPLICATION_TRACER_NAME on the span side. It is deliberately NOT
# what decides the boundary -- see below.
OPERATOR_LOG_SCOPE = "langflow.observability"

# The declared opt-in that lets a record's body leave the process. Bound by ``operator_logger()``
# and stripped here before anything renders it.
#
# A marker rather than a name match, which was the first design and was wrong. The obvious
# implementation is ``ApplicationOnlySpanProcessor``'s rule -- allowlist the scope -- but a log
# record's scope is *derived*, not declared: ``add_logger_name`` takes it from the bound logger,
# and under ``structlog.stdlib.LoggerFactory`` (which this module installs whenever a log file is
# configured) it is inferred from the calling module. So a module that merely happened to be
# named ``langflow.observability`` would have exported every one of its bodies verbatim without
# ever opting in, and this repo already has ``lfx/observability.py``,
# ``lfx/observability_doctor.py`` and ``lfx/observability_fastapi.py``. That file is one PR away.
#
# The same derivation also means the default bucket is not one name: anonymous callers land on
# "lfx", the module-global logger under a stdlib factory lands on "lfx.log.logger". Denying by
# default and requiring a positive marker makes the decision independent of both.
_OTEL_EXPORT_BODY_KEY = "_otel_export_body"

# Not a sandbox, and not claimed to be: any code in the process can bind the same key, including
# user-authored custom components, which already execute arbitrary Python here and could build
# their own exporter regardless. What it buys is that the whole verbatim-export surface is one
# grep for a single constant rather than a judgement about every log call in the codebase.

# Attributes a withheld record still carries. Every one is an identifier by construction -- a
# scope name, a module path, a line number, a service name -- so the set is safe to export
# without inspecting any value. Anything not named here is dropped, which means a new key added
# to the event dict later fails closed instead of silently joining the export.
_OTEL_SKELETON_KEYS = frozenset(
    {"logger", "service", "version", "environment", "pathname", "filename", "func_name", "lineno", "module"}
)

# Carries the way back in, because the operator who needs it is reading this string in an
# APM at 3am, not the boot line they would have to go and find.
_OTEL_WITHHELD_BODY = "[body withheld; set LANGFLOW_OTEL_LOG_BODIES=all to export bodies]"

_OTEL_BODY_POLICY_DEFAULT = "allowlist"
_OTEL_BODY_POLICIES = ("allowlist", "all")
_otel_body_policy_cache: str | None = None

# An exception chain is a linked list an application controls, so treat its length as untrusted.
_MAX_ERROR_CHAIN_DEPTH = 10

# Yielded in place of a link when the walk hit the bound, so a partial chain is never reported
# as a complete one. A sentinel exception instance rather than None, because None is a legal
# thing to find on __cause__ and would read as "the walk finished".
_CHAIN_TRUNCATED = BaseException()

# Whose ``code`` may be read at all. This is the boundary; the shape check below is only a
# second filter behind it.
#
# Shape is not a privacy boundary, and the first version of this treated it as one. Any exception
# carrying a ``.code`` was read, so a user-authored component could set
# ``err.code = "sk-abcdefghijklmnop"`` or an identifier-shaped prompt and it exported cleanly
# past the body withholding, because those look exactly like ``context_length_exceeded`` to a
# regex. Naming the modules instead means the value comes from a vendor's own documented
# vocabulary rather than from anything in the flow.
#
# Root package of ``type(exc).__module__``. Deliberately short: an SDK earns a place here once
# someone has checked that its ``code`` is a closed vocabulary and not a passthrough of the
# request. Being absent costs one attribute; being wrongly present costs a leak.
_PROVIDER_SDK_MODULES = frozenset({"openai", "anthropic"})

# The exact codes that may be exported. Not a pattern: the value is whatever the server put in
# the response JSON, and the SDK parrots it, so shape says nothing about where it came from.
#
# That is the part the module check alone missed. Langflow supports OpenAI-compatible endpoints
# through OPENAI_BASE_URL, so a genuine openai.BadRequestError can carry a code that a
# self-hosted or hostile endpoint chose. Matching against a fixed set defined here means the
# exported string is one we wrote, and nothing from the wire can pass through it.
#
# Drawn from the documented vocabularies and kept to codes that answer an operator's question:
# is this us, the customer's input, or the provider. An unlisted code exports nothing rather
# than being trusted, which costs one attribute and closes the channel.
# Mapped to itself so the lookup returns the literal written here rather than the caller's
# object. Exporting the input, even after it compares equal, hands the wire back its own value.
_KNOWN_PROVIDER_ERROR_CODES = {
    code: code
    for code in (
        "content_filter",
        "context_length_exceeded",
        "insufficient_quota",
        "invalid_api_key",
        "invalid_function_parameters",
        "invalid_request_error",
        "missing_required_parameter",
        "model_not_found",
        "rate_limit_exceeded",
        "server_error",
        "string_above_max_length",
        "unknown_parameter",
        "unsupported_value",
    )
}

_HTTP_STATUS_MIN = 100
_HTTP_STATUS_MAX = 599

# A ``sys.exc_info()`` triple: (type, value, traceback).
_EXC_INFO_TRIPLE_LEN = 3


def _otel_body_policy() -> str:
    """Resolve whether log bodies may be exported, and say so out loud when they may.

    Resolved and cached once, for the same reasons as :func:`_otel_min_severity`: it runs on
    every exported record, it cannot change without a restart, and caching before the warning
    keeps a warning that gets routed back into logging from recursing.

    ``all`` restores the pre-boundary behaviour wholesale. It is allowed because an operator
    debugging a live incident may genuinely need the provider's error text, and refusing
    outright would only get worked around by turning the whole signal off, which is worse. But
    it re-opens the channel that carries prompts and completions, so it must never happen
    quietly. An unrecognised value falls back to the safe policy, so a typo cannot open it.
    """
    global _otel_body_policy_cache  # noqa: PLW0603
    if _otel_body_policy_cache is not None:
        return _otel_body_policy_cache

    raw = os.getenv("LANGFLOW_OTEL_LOG_BODIES", _OTEL_BODY_POLICY_DEFAULT).strip().lower()
    policy = raw if raw in _OTEL_BODY_POLICIES else None
    _otel_body_policy_cache = policy or _OTEL_BODY_POLICY_DEFAULT

    with contextlib.suppress(Exception):
        if policy is None:
            warnings.warn(
                f"LANGFLOW_OTEL_LOG_BODIES: ignoring {raw!r} (expected one of "
                f"{list(_OTEL_BODY_POLICIES)}); withholding bodies from all but allowlisted scopes.",
                stacklevel=2,
            )
        elif policy == "all":
            warnings.warn(
                "LANGFLOW_OTEL_LOG_BODIES=all exports log message bodies to the configured OTLP "
                "endpoint. Langflow error messages carry model completions, chat history and "
                "provider responses, and redaction only covers known sensitive keys, not free "
                "text inside a message, so prompt and completion content will reach that "
                "backend. Leave it unset unless that is intended.",
                stacklevel=2,
            )
    return _otel_body_policy_cache


def _callsite_adder() -> Any:
    """Where the record came from, which is what makes a withheld body still actionable.

    ``PATHNAME`` alongside ``FILENAME`` because ``MODULE`` is the filename stem, not the dotted
    path: ``graph/vertex/base.py`` and ``graph/graph/base.py`` both report ``base``, and telling
    those apart is most of the value here.

    ``additional_ignores`` matters for foreign records. A stdlib log line reaches structlog
    through ``InterceptHandler`` in this module, so without it every uvicorn, sqlalchemy and
    httpx record reports this file's own emit call as its callsite -- a constant, and a wrong
    one, written into stdout and the JSON file as well as OTLP.
    """
    parameter = structlog.processors.CallsiteParameter
    return structlog.processors.CallsiteParameterAdder(
        parameters=[
            parameter.PATHNAME,
            parameter.FILENAME,
            parameter.FUNC_NAME,
            parameter.LINENO,
            parameter.MODULE,
        ],
        additional_ignores=[__name__, "logging"],
    )


def _otlp_logs_configured() -> bool:
    """Whether this process will actually ship logs over OTLP.

    Resolved through ``lfx.observability`` rather than by reading the environment here, so the
    answer cannot drift from the bootstrap's. Those two helpers sit outside that module's
    otel-guarded block precisely so callers like this one can import them without OpenTelemetry
    installed. The import is deferred to call time because observability imports this module.
    """
    try:
        from lfx.observability import otlp_endpoint, otlp_exporter_disabled
    except ImportError:  # pragma: no cover - lfx.observability ships with lfx
        return False
    return bool(otlp_endpoint("logs")) and not otlp_exporter_disabled("logs")


def _exception_from(exc_info: Any) -> BaseException | None:
    """Recover the exception behind a structlog ``exc_info`` value, in any of its shapes.

    ``logger.exception()`` sets it to ``True`` and leaves resolution to a renderer that has not
    run yet at this point in the chain; an explicit ``exc_info=`` may be the exception itself or
    a ``sys.exc_info()`` triple.
    """
    if exc_info is None or exc_info is False:
        return None
    if exc_info is True:
        return sys.exc_info()[1]
    if isinstance(exc_info, BaseException):
        return exc_info
    if isinstance(exc_info, tuple) and len(exc_info) == _EXC_INFO_TRIPLE_LEN and isinstance(exc_info[1], BaseException):
        return exc_info[1]
    return None


def _exception_chain(exc: BaseException) -> Iterator[BaseException]:
    """Walk an exception to its root cause, yielding each link outer to inner.

    One traversal, two readers: the class names and the transport identity below both depend on
    where the walk stops, and two copies of these rules would eventually disagree about it.

    ``__cause__`` wins over ``__context__``, so an explicit ``raise ... from ...`` is followed in
    preference to whatever happened to be in flight, and ``__suppress_context__`` ends the walk.
    That last part is not a detail: every provider SDK built on httpx raises its own error with
    ``from None`` inside an ``except httpx.HTTPStatusError`` block, so following a suppressed
    context reports ``HTTPStatusError`` as the root of a rate limit, a bad request and an auth
    failure alike. There are another 39 ``from None`` sites in lfx and langflow. ``traceback``
    makes the same choice.

    Bounded and cycle-guarded, because the chain is built by application code and a
    self-referencing ``__context__`` is reachable. Yields ``_CHAIN_TRUNCATED`` last when it hit
    the bound, so a caller can say so rather than presenting a partial answer as a complete one.
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if len(seen) >= _MAX_ERROR_CHAIN_DEPTH:
            yield _CHAIN_TRUNCATED
            return
        seen.add(id(current))
        yield current
        if current.__cause__ is not None:
            current = current.__cause__
        elif current.__suppress_context__:
            return
        else:
            current = current.__context__


def _error_identity(exc: BaseException) -> tuple[str, str]:
    """Reduce an exception to class names: the root cause, and the chain that wrapped it.

    The root cause is the point of this. Langflow wraps aggressively -- a provider's rate limit
    surfaces as ``ComponentBuildError`` at the run boundary -- so the outermost class names our
    catch site and is identical for every failing flow, while the innermost names the failure.
    Reporting the chain outer-to-inner as well keeps the wrapping visible without costing
    anything, because a class name is an identifier and carries no message text.

    Traversal rules, and why the walk stops where it does, are on :func:`_exception_chain`.
    Hitting its bound appends an ellipsis so a truncated chain is never read as a complete one.

    The root is returned fully qualified, per OTel's ``error.type``: three unrelated
    ``TimeoutError`` classes (builtins, asyncio, sqlalchemy.exc) collapse to one string
    otherwise, and telling a pool exhaustion from a socket timeout is the whole point. The chain
    keeps bare names so it stays readable. Builtins are left unqualified because
    ``builtins.ValueError`` is noise.

    A class name is an identifier, which is why this is safe to export where the message is not.
    The one wrinkle, shared with the ``error.type`` the span path already exports: a user-authored
    component can define its own exception class, so the name is user-chosen even though it is not
    user *data*. Measured and accepted rather than assumed.
    """
    chain: list[str] = []
    root = exc
    truncated = True
    for link in _exception_chain(exc):
        if link is _CHAIN_TRUNCATED:
            break
        chain.append(type(link).__name__)
        root = link
    else:
        truncated = False

    module = type(root).__module__
    qualified = type(root).__qualname__ if module == "builtins" else f"{module}.{type(root).__qualname__}"
    return qualified, "<".join([*chain, "..."]) if truncated else "<".join(chain)


def _error_transport_identity(exc: BaseException) -> dict[str, str | int]:
    """The HTTP status and provider error code, when something in the chain carries them.

    ``error.type`` separates a rate limit from a timeout, and stops there. It cannot separate two
    failures that share a class, and the pair that matters most does: a context-length rejection
    and an invalid tool schema are both ``openai.BadRequestError`` with the same 400, the same
    scope and the same callsite. One is the customer's conversation growing too long and the
    other is a bug we shipped, so they route to different people, and with the message withheld
    nothing else tells them apart.

    The SDKs expose the discriminator structurally: ``status_code`` and ``code``
    (``context_length_exceeded``, ``invalid_function_parameters``). Those are provider
    vocabulary, not user text, which is what makes them exportable on the same terms as a class
    name.

    Read by attribute only. The same information also sits in ``exc.body["error"]["code"]``, but
    that dict's sibling ``message`` is the prompt tail, and a boundary that reaches into a
    payload to pull one key out is one refactor away from taking the payload.

    ``code`` must be an exact ``str`` matching ``_KNOWN_PROVIDER_ERROR_CODES``, on an exception
    belonging to one of ``_PROVIDER_SDK_MODULES``, and what is exported is the literal from that
    mapping rather than the value handed in. The value allowlist is the boundary, because neither
    shape nor source is one: the SDK copies ``code`` out of the response JSON, and Langflow can be
    pointed at any OpenAI-compatible endpoint, so a genuine ``openai.BadRequestError`` can carry a
    string the server chose. Matching a fixed set means the exported value is one written here.

    The module check stays in front of it. It buys nothing against a leak once the value is
    fixed, but it stops a component raising its own error with ``code="rate_limit_exceeded"``
    from putting a false provider signal on an operator's dashboard.

    ``status_code`` needs neither, being an int bounded to the HTTP range.
    """
    attributes: dict[str, str | int] = {}
    for link in _exception_chain(exc):
        if link is _CHAIN_TRUNCATED:
            break
        if "http.response.status_code" not in attributes:
            status = _first_int(link, ("status_code",)) or _first_int(getattr(link, "response", None), ("status_code",))
            if status is not None and _HTTP_STATUS_MIN <= status <= _HTTP_STATUS_MAX:
                attributes["http.response.status_code"] = status
        if "error.code" not in attributes and type(link).__module__.split(".")[0] in _PROVIDER_SDK_MODULES:
            code = getattr(link, "code", None)
            # `type(...) is str`, not isinstance: a str subclass can override __hash__ and
            # __eq__, so it compares equal to an allowlisted code while carrying something else,
            # and the lookup would then export the object rather than the match. One that raises
            # from __hash__ is worse than a leak in a different direction: it propagates into the
            # caller's broad except and drops the whole record.
            #
            # `code` is whatever was in the response JSON, so it can equally be a dict or a list.
            # The type check covers that too.
            canonical = _KNOWN_PROVIDER_ERROR_CODES.get(code) if type(code) is str else None
            if canonical is not None:
                attributes["error.code"] = canonical
    return attributes


def _first_int(source: Any, names: tuple[str, ...]) -> int | None:
    """Read the first of *names* off *source* that is a plain int.

    ``getattr`` on a third-party exception can run a property, so it is guarded: telemetry must
    never be the thing that turns a handled provider error into an unhandled one. Suppressed
    rather than logged, because this runs inside the log processor chain and reporting it would
    re-enter here. ``bool`` is excluded because it is an ``int`` and a status of ``True`` is
    nonsense.
    """
    for name in names:
        value = None
        with contextlib.suppress(Exception):
            value = getattr(source, name, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def emit_to_otel_logs(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Ship the record to the configured OTel log pipeline, then hand it back unchanged.

    A pass-through: this sits in the processor chain purely for the side effect, so console
    and file output are unaffected. When no SDK logger provider is installed -- bare lfx, or
    Langflow with no OTLP endpoint configured -- ``get_logger`` returns a no-op and this costs
    one attribute lookup.

    Placed after the redaction processor so anything scrubbed there is scrubbed here too.
    Trace correlation is left to the SDK, which reads the active span from the context, so a
    log line emitted inside a flow execution lands on that flow's trace in the APM.

    The body only leaves the process when its scope is allowlisted. Severity decides whether a
    record is exported at all; this decides whether its text is, and the two are separate because
    an operator wants to know a request failed at ERROR whether or not they are allowed to see
    the sentence describing it. A withheld record is not a dropped one -- it keeps its severity,
    scope, callsite, root-cause class and trace correlation, which is what a pivot from a failed
    trace actually needs.
    """
    if _otel_logs is None:
        return event_dict

    severity = _OTEL_LOG_SEVERITY.get(str(event_dict.get("level", "")).lower())
    if severity is None or severity < _otel_min_severity():
        return event_dict

    # Popped, not read: the marker is an instruction to this processor and must not reach the
    # console renderer, the JSON file or the log buffer.
    declared = event_dict.pop(_OTEL_EXPORT_BODY_KEY, False) is True
    export_body = declared or _otel_body_policy() == "all"
    # Anonymous callers have no logger name; group them under the package rather than "".
    scope = event_dict.get("logger") or "lfx"

    try:
        if export_body:
            body = str(event_dict.get("event", ""))
            keep = event_dict.items()
        else:
            body = _OTEL_WITHHELD_BODY
            keep = ((k, v) for k, v in event_dict.items() if k in _OTEL_SKELETON_KEYS)

        attributes = {
            k: v if isinstance(v, str | bool | int | float) else str(v)
            for k, v in keep
            if k not in _OTEL_LOG_SKIP_KEYS and v is not None
        }

        # Derived last so it wins: these are the trustworthy names, and an event dict carrying
        # its own "error.type" key would otherwise shadow the one read off the live exception.
        exception = _exception_from(event_dict.get("exc_info"))
        if exception is not None:
            root, chain = _error_identity(exception)
            attributes["error.type"] = root
            if chain != root:
                attributes["error.chain"] = chain
            attributes.update(_error_transport_identity(exception))

        otel_logger = _otel_logs.get_logger(scope)
        otel_logger.emit(
            body=body,
            severity_number=_OtelSeverity(severity),
            severity_text=str(event_dict.get("level", "")).upper(),
            attributes=attributes,
        )
    except Exception:  # noqa: BLE001 - logging must never break on a flaky exporter
        return event_dict
    return event_dict


def otel_log_bodies_exported() -> bool:
    """Whether message bodies leave the process for scopes that are not allowlisted.

    Public because the bootstrap states the boundary in its startup line and must describe the
    policy actually in force, not the default.
    """
    return _otel_body_policy() == "all"


def operator_logger() -> Any:
    """A logger whose message bodies are allowed to cross the OTLP boundary.

    For operator statements about the runtime itself -- what got configured, what is exporting
    where -- which are assembled from constants and identifiers and carry no flow data. Anything
    that formats a component's output, a provider response or an exception message belongs on
    the ordinary module-level ``logger`` instead, where the body is withheld.

    The scope name is for grouping in the APM; the bound marker is what actually opts the body
    in, so this cannot be obtained by naming a module after the scope.
    """
    return structlog.get_logger(OPERATOR_LOG_SCOPE).bind(**{_OTEL_EXPORT_BODY_KEY: True})


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

    # Add callsite information when LANGFLOW_DEV is set, and when logs are being exported over
    # OTLP. In the second case it is what makes a withheld record actionable: severity and scope
    # alone do not tell an operator which line produced the failure, and the body that used to
    # tell them is no longer leaving the process. Costs a frame walk per record, which is why it
    # stays off for a deployment that is not exporting logs anywhere.
    if DEV or _otlp_logs_configured():
        processors.append(_callsite_adder())

    processors.extend(
        [
            redact_processor,
            # After redaction, before rendering: the APM must not see anything the console
            # would have scrubbed, and the renderers below replace `event` with a formatted
            # string, which would lose the structure.
            emit_to_otel_logs,
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
                # Foreign records reach OTLP through this chain, not the one above, so without
                # the adder here they would export with no callsite at all -- and the callsite
                # is what a withheld body leaves an operator to work with.
                *([_callsite_adder()] if DEV or _otlp_logs_configured() else []),
                emit_to_otel_logs,
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
