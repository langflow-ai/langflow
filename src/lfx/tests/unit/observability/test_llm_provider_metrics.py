"""Leak-safe LLM-provider metrics: real instruments, real reader, no mocking.

The crux is the leak/cardinality assertion: every attribute across every data point must be one
of three known-safe keys, and no value may carry a URL, a prompt, or an API key. That is the
guarantee PR #14213 removed the httpx span path to protect, restated as a runtime check.
"""

import importlib.util

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.outputs import Generation, LLMResult

_HAS_OTEL = importlib.util.find_spec("opentelemetry") is not None
pytestmark = pytest.mark.skipif(not _HAS_OTEL, reason="requires the lfx[otel] extra")

_ALLOWED_KEYS = {"gen_ai.provider.name", "gen_ai.request.model", "error.type"}


@pytest.fixture(scope="module")
def reader():
    """Install a real meter provider once before any handler reads the global meter.

    The global meter provider can only be set once per process (the SDK refuses to override),
    so this is module-scoped. Each test constructs a fresh handler and uses distinct run_ids;
    the reader is cumulative, so assertions read the point matching what the test just recorded.
    """
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    in_memory = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[in_memory])
    metrics.set_meter_provider(provider)
    yield in_memory
    provider.shutdown()


def _all_data_points(reader):
    data = reader.get_metrics_data()
    points = {}  # metric name -> list of data points
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                points.setdefault(metric.name, []).extend(metric.data.data_points)
    return points


def test_success_records_duration_with_exact_attributes(reader):
    from lfx.observability_llm_metrics import LLMProviderMetricsCallbackHandler

    h = LLMProviderMetricsCallbackHandler()
    import uuid

    rid = uuid.uuid4()
    h.on_chat_model_start(
        {}, [[HumanMessage("super secret prompt")]], run_id=rid, invocation_params={"model_name": "gpt-4o"}
    )
    h.on_llm_end(LLMResult(generations=[[Generation(text="hi")]]), run_id=rid)

    points = _all_data_points(reader)
    duration_points = points.get("gen_ai.client.operation.duration", [])
    assert duration_points, "expected a duration histogram data point"
    dp = duration_points[0]
    assert dict(dp.attributes) == {"gen_ai.provider.name": "openai", "gen_ai.request.model": "gpt-4o"}
    assert dp.count > 0


def test_error_records_counter_with_error_type(reader):
    from lfx.observability_llm_metrics import LLMProviderMetricsCallbackHandler

    h = LLMProviderMetricsCallbackHandler()
    import uuid

    rid = uuid.uuid4()
    h.on_chat_model_start({}, [[HumanMessage("x")]], run_id=rid, invocation_params={"model_name": "claude-3-5-sonnet"})
    h.on_llm_error(RuntimeError("boom https://api.openai.com/v1/chat?key=sk-SECRET-LEAK"), run_id=rid)

    points = _all_data_points(reader)
    error_points = points.get("langflow.llm.provider.errors", [])
    assert error_points, "expected an error counter data point"
    attrs = dict(error_points[0].attributes)
    assert attrs["error.type"] == "RuntimeError"
    assert attrs["gen_ai.provider.name"] == "anthropic"

    # Failed-call latency ("is it us or them" case) must land on the duration histogram too,
    # carrying error.type per the OTel GenAI semconv.
    error_durations = [
        dp for dp in points.get("gen_ai.client.operation.duration", []) if dict(dp.attributes).get("error.type")
    ]
    assert error_durations, "expected a duration point for the failed call"
    assert dict(error_durations[0].attributes)["error.type"] == "RuntimeError"


def test_cancelled_runs_do_not_grow_unbounded():
    """A run that never reaches on_llm_end/on_llm_error (cancelled mid-flight) must not leak forever."""
    from lfx.observability_llm_metrics import LLMProviderMetricsCallbackHandler

    h = LLMProviderMetricsCallbackHandler()
    h._MAX_RUNS = 2  # instance override so the cap is reachable in a test
    import uuid

    for _ in range(5):
        h.on_chat_model_start(
            {}, [[HumanMessage("x")]], run_id=uuid.uuid4(), invocation_params={"model_name": "gpt-4o"}
        )
    assert len(h._runs) <= 2


def test_no_leak_and_bounded_cardinality(reader):
    """Walk every attribute of both metrics: keys are a known subset, values carry no secrets."""
    from lfx.observability_llm_metrics import LLMProviderMetricsCallbackHandler

    h = LLMProviderMetricsCallbackHandler()
    import uuid

    rid = uuid.uuid4()
    h.on_chat_model_start(
        {}, [[HumanMessage("super secret prompt")]], run_id=rid, invocation_params={"model_name": "gpt-4o"}
    )
    h.on_llm_end(LLMResult(generations=[[Generation(text="hi")]]), run_id=rid)

    rid2 = uuid.uuid4()
    h.on_chat_model_start({}, [[HumanMessage("y")]], run_id=rid2, invocation_params={"model_name": "claude-3-5-sonnet"})
    h.on_llm_error(RuntimeError("boom https://api.openai.com/v1/chat?key=sk-SECRET-LEAK"), run_id=rid2)

    for metric_points in _all_data_points(reader).values():
        for dp in metric_points:
            for key, value in dict(dp.attributes).items():
                assert key in _ALLOWED_KEYS, f"unexpected attribute key: {key}"
                text = str(value)
                assert "sk-SECRET-LEAK" not in text
                assert "http" not in text
                assert "super secret prompt" not in text
