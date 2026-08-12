"""What crosses the OTLP logs boundary.

The span exporter allowlists by instrumentation scope; the logs exporter withholds bodies
unless a call site declares the opt-in, because a log record's scope is derived rather than
declared and a look-alike module name would otherwise be enough.
These tests are the executable form of the claim the vendor documentation makes, so they assert
both halves: that flow-derived text does not leave, and that a withheld record still carries
enough for an operator to act on. Only asserting the first half would pass if the signal were
broken entirely, which is why every negative here is paired with a positive.

Each case runs in a subprocess because the logger provider is process-global and the body policy
is resolved from the environment once and cached for the life of the process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry")

# Distinctive enough that a substring match against the whole exported payload cannot collide
# with anything the runtime emits on its own.
PROMPT = "SENTINELPROMPTQQQ"
EXC_MESSAGE = "SENTINELEXCMSGQQQ"

PROBE = '''
import json, os, sys

from opentelemetry import _logs
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogExporter, SimpleLogRecordProcessor

exporter = InMemoryLogExporter()
provider = LoggerProvider()
provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
_logs.set_logger_provider(provider)

from lfx.log.logger import configure, logger, operator_logger

configure(log_level="INFO", log_env="container")


class ProviderError(Exception):
    pass


class ComponentBuildError(Exception):
    pass


def wrapped_failure():
    """The real shape: a provider error surfaced at the run boundary as a build error.

    Raised rather than constructed, because ``raise ... from`` is what sets ``__cause__`` and
    the chain walk has nothing to follow otherwise.
    """
    try:
        try:
            raise ProviderError("rate limited, request was SENTINELEXCMSGQQQ")
        except ProviderError as inner:
            raise ComponentBuildError(f"Error building Component Failing: {inner}") from inner
    except ComponentBuildError as outer:
        return outer


# An ordinary call site interpolating the user's prompt into the message.
logger.error("Error running flow: input was SENTINELPROMPTQQQ")

# An exception passed explicitly, which is the form that put the message in an attribute.
logger.error("component failed", exc_info=wrapped_failure())

# An operator statement, which declares the opt-in.
operator_logger().info("OTLP log export enabled (endpoint=https://collector:4318).")

# A caller that only borrows the scope NAME, without declaring anything.
if os.environ.get("PROBE_SQUAT"):
    import structlog

    structlog.get_logger("langflow.observability").error("SQUATTEDBODYQQQ")

# The real agent failure shape, since that is the record an on-call actually lands on.
if os.environ.get("PROBE_AGENT"):
    from lfx.base.agents.events import ExceptionWithMessageError
    from lfx.schema.message import Message

    class RateLimitError(Exception):
        pass

    partial = Message(text="SENTINELCOMPLETIONQQQ as far as the model had streamed")
    try:
        try:
            raise RateLimitError("429 slow down")
        except RateLimitError as provider_error:
            raise ExceptionWithMessageError(partial, "agent step failed") from provider_error
    except ExceptionWithMessageError:
        # Mirrors base/agents/agent.py after the call sites stopped formatting the exception.
        logger.exception("Agent run failed after a partial message was emitted")

provider.force_flush()

records = [
    {
        "scope": item.instrumentation_scope.name if item.instrumentation_scope else None,
        "severity": item.log_record.severity_text,
        "body": item.log_record.body,
        "attributes": {k: str(v) for k, v in (item.log_record.attributes or {}).items()},
    }
    for item in exporter.get_finished_logs()
]
print("PROBE_RESULT " + json.dumps(records))
'''


def run_probe(**env_overrides: str) -> list[dict]:
    """Run the probe in a clean interpreter and return the records it exported."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OTEL_", "LANGFLOW_OTEL_"))}
    # Callsite capture is gated on logs actually being exported somewhere.
    env["OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"] = "http://localhost:4318"
    env.update(env_overrides)

    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe.py"
        probe.write_text(PROBE, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe)],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    return json.loads(line.removeprefix("PROBE_RESULT "))


def application_records(records: list[dict]) -> list[dict]:
    return [r for r in records if r["scope"] != "langflow.observability"]


def test_prompt_and_exception_text_do_not_leave_the_process():
    """The claim itself: what the span boundary withholds, the log boundary now withholds too."""
    payload = json.dumps(run_probe())

    assert PROMPT not in payload
    assert EXC_MESSAGE not in payload


def test_a_withheld_record_is_still_actionable():
    """A boundary that exported nothing would pass the test above and be useless.

    Severity, scope, callsite and root cause are what an operator pivots to from a failed trace,
    and none of them is free text.
    """
    records = application_records(run_probe())

    assert records, "application records must still be exported, only their bodies withheld"
    assert all(r["severity"] == "ERROR" for r in records)
    assert all(r["attributes"].get("module") for r in records)
    assert all(r["attributes"].get("lineno") for r in records)

    with_exception = [r for r in records if "error.type" in r["attributes"]]
    assert with_exception, "a record carrying an exception must report its type"


def test_error_type_is_the_root_cause_not_the_wrapper():
    """Langflow wraps aggressively, so the outermost class names our catch site, not the failure.

    Without this an operator cannot tell a rate limit from a bad request, which is most of what
    the withheld message used to tell them. Qualified per OTel's error.type, so the probe's own
    module prefixes it.
    """
    records = application_records(run_probe())
    attributes = next(r["attributes"] for r in records if "error.type" in r["attributes"])

    assert attributes["error.type"].endswith("ProviderError")
    assert not attributes["error.type"].endswith("ComponentBuildError")
    assert attributes["error.chain"] == "ComponentBuildError<ProviderError"


def test_a_suppressed_context_is_not_reported_as_the_root():
    """``raise ... from None`` means the inner error is deliberately not the story.

    This is not a corner case: every provider SDK built on httpx raises its own error that way
    inside an ``except httpx.HTTPStatusError`` block, so following a suppressed context reports
    HTTPStatusError as the root of a rate limit, a bad request and an auth failure alike.
    """
    from lfx.log.logger import _error_identity

    dropped = "provider detail that was deliberately dropped"
    surfaced = "the error we chose to surface"
    try:
        try:
            raise ValueError(dropped)
        except ValueError:
            raise RuntimeError(surfaced) from None
    except RuntimeError as exc:
        root, chain = _error_identity(exc)

    assert root == "RuntimeError"
    assert chain == "RuntimeError"


def test_a_truncated_chain_says_so():
    """Reporting the deepest link seen as though it were the root would be a quiet lie."""
    from lfx.log.logger import _MAX_ERROR_CHAIN_DEPTH, _error_identity

    current: BaseException = ValueError("root")
    for index in range(_MAX_ERROR_CHAIN_DEPTH + 5):
        wrapper = f"wrapper {index}"
        try:
            raise RuntimeError(wrapper) from current
        except RuntimeError as exc:
            current = exc

    _, chain = _error_identity(current)

    assert chain.endswith("<...")


def test_a_failing_agent_run_exports_an_error_type_and_not_the_completion():
    """The real exception class an agent failure carries, put through the real boundary.

    ExceptionWithMessageError.__str__ interpolates the model's partial completion, and it wraps
    the provider's error, so it exercises both halves at once: the completion must not survive,
    and the provider class must still surface as the root rather than the wrapper.

    Asserted with bodies turned ON, deliberately. Under the default policy no body is exported
    at all, so "the completion is absent" would be trivially true and would pass against a call
    site that still formats the exception into its message. Bodies on is where an operator who
    opted in would actually see the leak, so it is the only place the absence means anything.

    Scope note, because the assertion looks broader than it is: this reproduces the *shape* of
    the agent catch sites, it does not drive them. It would still pass if a call site went back
    to error(f"...{e}"). Guarding that needs a source-level check, and ruff G004 is not it: it
    is inert here because logger-objects is unset, and even configured it does not know
    structlog's aerror/aexception, which is where four of the nine statements in this fix lived.
    """
    records = run_probe(PROBE_AGENT="1", LANGFLOW_OTEL_LOG_BODIES="all")
    payload = json.dumps(records)

    assert "SENTINELCOMPLETIONQQQ" not in payload

    agent_records = [r for r in records if "RateLimitError" in r["attributes"].get("error.type", "")]
    assert agent_records, "the agent failure record must carry the provider error as its root"
    assert agent_records[0]["attributes"]["error.chain"] == "ExceptionWithMessageError<RateLimitError"


def test_two_failures_that_share_a_class_are_still_told_apart():
    """error.type stops at the class, and the pair that matters most shares one.

    A context-length rejection and an invalid tool schema are both openai.BadRequestError with
    the same 400, the same scope and the same callsite. One is the customer's conversation
    growing too long and the other is a bug we shipped. Built from real SDK exceptions rather
    than a stand-in, because the whole claim is that these particular attributes exist.
    """
    httpx = pytest.importorskip("httpx")
    openai = pytest.importorskip("openai")

    from lfx.log.logger import _error_transport_identity

    def provider_error(code: str, status: int = 400, cls=None):
        body = {"error": {"message": "maximum context length is 8192, you requested 9134", "code": code}}
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        response = httpx.Response(status, request=request, json=body)
        return (cls or openai.BadRequestError)("boom", response=response, body=body["error"])

    too_long = _error_transport_identity(provider_error("context_length_exceeded"))
    bad_schema = _error_transport_identity(provider_error("invalid_function_parameters"))

    assert too_long["http.response.status_code"] == bad_schema["http.response.status_code"] == 400
    assert too_long["error.code"] != bad_schema["error.code"]
    assert too_long["error.code"] == "context_length_exceeded"


def test_the_provider_error_message_is_not_exported_alongside_the_code():
    """`code` and `message` are siblings in the same dict, and only one of them is safe."""
    httpx = pytest.importorskip("httpx")
    openai = pytest.importorskip("openai")

    from lfx.log.logger import _error_transport_identity

    body = {"error": {"message": "you requested 9134 tokens: SENTINELPROMPTQQQ", "code": "context_length_exceeded"}}
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    error = openai.BadRequestError("boom", response=httpx.Response(400, request=request, json=body), body=body["error"])

    assert PROMPT not in json.dumps(_error_transport_identity(error))


@pytest.mark.parametrize(
    "code",
    [
        "a sentence with spaces, and the prompt SENTINELPROMPTQQQ",
        "x" * 65,
        "",
        None,
        12345,
        {"nested": "object"},
    ],
)
def test_a_provider_error_code_that_is_not_identifier_shaped_is_dropped(code):
    """Nothing guarantees a field named `code` holds a code.

    The value is provider-controlled and travels to the operator's APM, so its shape is checked
    rather than the name trusted. Dropping it costs one attribute; exporting it on faith is how
    a payload gets through a boundary that was supposed to only pass identifiers.
    """
    from lfx.log.logger import _error_transport_identity

    class ProviderError(Exception):
        pass

    error = ProviderError("boom")
    error.code = code

    assert "error.code" not in _error_transport_identity(error)


# The verbatim-export surface, checked in source rather than described in a comment.
#
# The design note on APPLICATION_LOG_SCOPES says the point of a declared marker is that the whole
# surface is "one grep for a single constant". That is only worth anything if someone runs the
# grep, so this is it. Everything else in this file asserts what the exporter does with a record;
# this asserts how many places can produce the kind of record that keeps its body.
#
# Two ways in, so both are covered: calling operator_logger(), and binding the marker key
# directly, which would sidestep the helper entirely.
BODY_EXPORT_OWNERS = frozenset({"observability.py"})
MARKER_OWNERS = frozenset({"logger.py"})


def _source_roots() -> list[Path]:
    """The packages whose call sites matter: lfx, and langflow when its source is present."""
    src = Path(__file__).resolve().parents[4]
    candidates = [src / "lfx" / "src" / "lfx", src / "backend" / "base" / "langflow"]
    return [path for path in candidates if path.is_dir()]


def _calls_and_marker_uses(path: Path) -> tuple[list[int], list[int]]:
    """Line numbers where *path* calls operator_logger, and where it names the marker key."""
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    calls: list[int] = []
    markers: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name == "operator_logger":
                calls.append(node.lineno)
            markers.extend(node.lineno for kw in node.keywords if kw.arg == "_otel_export_body")
        elif isinstance(node, ast.Constant) and node.value == "_otel_export_body":
            markers.append(node.lineno)
    return calls, markers


def test_only_the_bootstrap_can_export_a_log_body_verbatim():
    """A new caller is a decision to export somebody's message text, so it should not be quiet.

    Adding a legitimate one means adding its filename here, in a diff that says so.
    """
    roots = _source_roots()
    assert roots, "found no source tree to scan; the path assumption in _source_roots is wrong"

    offenders = [
        f"{path}:{line}"
        for root in roots
        for path in sorted(root.rglob("*.py"))
        for line in _calls_and_marker_uses(path)[0]
        if path.name not in BODY_EXPORT_OWNERS | MARKER_OWNERS
    ]

    assert not offenders, (
        "operator_logger() exports the message body verbatim to the operator's APM. "
        f"New call sites outside {sorted(BODY_EXPORT_OWNERS)}:\n  " + "\n  ".join(offenders)
    )


def test_the_marker_key_is_not_bound_outside_the_logger():
    """Binding the key by hand reaches the same place as operator_logger, without passing it."""
    offenders = [
        f"{path}:{line}"
        for root in _source_roots()
        for path in sorted(root.rglob("*.py"))
        for line in _calls_and_marker_uses(path)[1]
        if path.name not in MARKER_OWNERS
    ]

    assert not offenders, "the body-export marker is bound outside the logger:\n  " + "\n  ".join(offenders)


def test_the_scan_finds_the_call_sites_that_are_supposed_to_be_there():
    """The control. Both tests above assert an absence, and a scan that reads nothing is empty too."""
    roots = _source_roots()
    known = [
        (path, calls)
        for root in roots
        for path in sorted(root.rglob("*.py"))
        if (calls := _calls_and_marker_uses(path)[0]) and path.name in BODY_EXPORT_OWNERS
    ]

    assert known, "the scan found no operator_logger() calls at all, so it proves nothing"


def test_naming_a_module_after_the_scope_does_not_export_its_bodies():
    """The boundary is a declared marker, not a name match.

    A log record's scope is derived -- from the bound logger, or under the stdlib factory from
    the calling module -- so matching on it would mean a file added at
    langflow/observability.py exported every one of its bodies without opting in.
    """
    records = run_probe(PROBE_SQUAT="1")
    squatted = [r for r in records if r["body"] == "SQUATTEDBODYQQQ"]

    assert not squatted, "a look-alike scope name must not export its body"


def test_an_allowlisted_scope_still_exports_its_body():
    """The allowlist has to actually let something through, or it is just an off switch."""
    records = run_probe()
    operator = [r for r in records if r["scope"] == "langflow.observability"]

    assert len(operator) == 1
    assert "OTLP log export enabled" in operator[0]["body"]


def test_bodies_can_be_turned_back_on_deliberately():
    """The escape hatch, and the control for every negative assertion above.

    If the probe could not observe a leak, the tests that assert absence would pass against a
    broken exporter. This one proves it observes exactly what the others say has gone.
    """
    payload = json.dumps(run_probe(LANGFLOW_OTEL_LOG_BODIES="all"))

    assert PROMPT in payload


def test_the_exception_attribute_channel_stays_closed_even_then():
    """``exc_info`` carried the message as an attribute regardless of the body policy.

    It is dropped unconditionally rather than as part of the body decision, because an operator
    asking for message bodies is not asking for a stringified traceback tuple.
    """
    payload = json.dumps(run_probe(LANGFLOW_OTEL_LOG_BODIES="all"))

    assert EXC_MESSAGE not in payload


def test_an_unrecognised_body_policy_fails_closed():
    """A typo in a Helm chart must not be the thing that opens the channel."""
    payload = json.dumps(run_probe(LANGFLOW_OTEL_LOG_BODIES="ALL_OF_THEM"))

    assert PROMPT not in payload


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        # The fabricated credential is the input under test, hence the allowlist pragma.
        (
            "https://user:sekrit@otlp.example.com:4318/v1/logs",  # pragma: allowlist secret
            "https://otlp.example.com:4318/v1/logs",
        ),
        ("https://otlp.example.com/v1/logs?api-key=sekrit", "https://otlp.example.com/v1/logs"),
        ("https://sekrit@otlp.example.com/v1/logs", "https://otlp.example.com/v1/logs"),
        ("https://otlp.example.com/v1/logs#sekrit", "https://otlp.example.com/v1/logs"),
        ("http://[fd00::1]:4318/v1/logs", "http://[fd00::1]:4318/v1/logs"),
        ("http://localhost:4318", "http://localhost:4318"),
        # urlsplit strips tab/CR/LF per WHATWG, which would rejoin whatever followed one of them
        # into the path and write it verbatim to the one exported scope.
        ("https://otlp.example.com/v1/logs\nInjected: sekrit", "<unparseable endpoint>"),
        ("https://otlp.example.com/v1/logs\rInjected: sekrit", "<unparseable endpoint>"),
        # No authority: urlsplit treats these as opaque and parks the whole value in `path`, so
        # a typo that drops the slashes would otherwise have printed the secret verbatim.
        ("https:sekrit", "<unparseable endpoint>"),
        ("mailto:sekrit@otlp.example.com", "<unparseable endpoint>"),
        ("sekrit", "<unparseable endpoint>"),
        ("", "<unparseable endpoint>"),
    ],
)
def test_the_startup_line_reports_an_endpoint_without_its_credentials(endpoint: str, expected: str):
    """That line is on the one scope exported verbatim, and vendors document tokens in the URL.

    Without this, closing the body boundary would open a credential leak through the very line
    announcing it.
    """
    from lfx.observability import safe_endpoint

    assert safe_endpoint(endpoint) == expected
    assert "sekrit" not in safe_endpoint(endpoint)
