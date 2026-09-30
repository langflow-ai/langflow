"""The tracer provider is process-global and installed once, so each case runs in a subprocess."""

import json
import os
import subprocess
import sys

import pytest

PROBE = """
import json, os
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from opentelemetry import trace

OpenTelemetry(prometheus_enabled=False)

provider = trace.get_tracer_provider()
result = {"provider": type(provider).__name__}
resource = getattr(provider, "resource", None)
if resource is not None:
    result["service_name"] = resource.attributes.get("service.name")
    result["deployment_environment"] = resource.attributes.get("deployment.environment")
processors = getattr(getattr(provider, "_active_span_processor", None), "_span_processors", ())
result["exporters"] = [type(p.span_exporter).__module__ for p in processors]
print("PROBE_RESULT " + json.dumps(result))
"""


def run_probe(env_overrides: dict[str, str]) -> dict:
    # Start from a clean slate so the developer's own OTEL_* vars cannot skew the result.
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env.update(env_overrides)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", PROBE],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    return json.loads(line.removeprefix("PROBE_RESULT "))


def test_no_endpoint_installs_no_provider():
    """Local and desktop runs set no OTEL_* vars and must stay inert."""
    result = run_probe({})
    assert result["provider"] == "ProxyTracerProvider"


@pytest.mark.parametrize("endpoint_var", ["OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"])
def test_endpoint_installs_sdk_provider(endpoint_var):
    result = run_probe({endpoint_var: "http://localhost:4318"})
    assert result["provider"] == "TracerProvider"
    assert result["service_name"] == "langflow"


def test_service_name_env_wins_over_default():
    result = run_probe(
        {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318", "OTEL_SERVICE_NAME": "my-langflow"},
    )
    assert result["service_name"] == "my-langflow"


def test_resource_attributes_env_wins_over_default():
    result = run_probe(
        {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
            "OTEL_RESOURCE_ATTRIBUTES": "service.name=from-attrs,deployment.environment=prod",
        },
    )
    assert result["service_name"] == "from-attrs"
    assert result["deployment_environment"] == "prod"


@pytest.mark.parametrize(
    ("resource_attributes", "expected"),
    [
        # A key that merely ends in service.name must not be mistaken for one.
        ("k8s.service.name=checkout", "langflow"),
        ("app.service.name=foo,deployment.environment=prod", "langflow"),
        # Spaces around the = are legal and the SDK strips them.
        ("service.name = spaced", "spaced"),
    ],
)
def test_service_name_is_not_matched_by_substring(resource_attributes, expected):
    result = run_probe(
        {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318", "OTEL_RESOURCE_ATTRIBUTES": resource_attributes},
    )
    assert result["service_name"] == expected


def test_empty_service_name_falls_back_to_default():
    result = run_probe({"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318", "OTEL_SERVICE_NAME": ""})
    assert result["service_name"] == "langflow"


@pytest.mark.parametrize(
    ("protocol", "expected"),
    [
        (None, "http"),
        ("http/protobuf", "http"),
        ("grpc", "grpc"),
    ],
)
def test_protocol_selects_exporter(protocol, expected):
    env = {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"}
    if protocol:
        env["OTEL_EXPORTER_OTLP_PROTOCOL"] = protocol
    result = run_probe(env)
    assert len(result["exporters"]) == 1
    assert f".proto.{expected}." in result["exporters"][0]


@pytest.mark.parametrize("protocol", [" grpc", "grpc ", "GRPC", "http/json", "nonsense"])
def test_unsupported_protocol_falls_back_to_http_without_misrouting(protocol):
    """A stray space must not silently point an HTTP exporter at a gRPC receiver."""
    result = run_probe(
        {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318", "OTEL_EXPORTER_OTLP_PROTOCOL": protocol},
    )
    expected = "grpc" if protocol.strip() == "grpc" else "http"
    assert f".proto.{expected}." in result["exporters"][0]


def test_traces_exporter_none_disables_export():
    """Operators disable traces this way when a shared config injects the endpoint."""
    result = run_probe(
        {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318", "OTEL_TRACES_EXPORTER": "none"},
    )
    assert result["provider"] == "ProxyTracerProvider"


def test_per_signal_protocol_takes_precedence():
    result = run_probe(
        {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "grpc",
        },
    )
    assert ".proto.grpc." in result["exporters"][0]
