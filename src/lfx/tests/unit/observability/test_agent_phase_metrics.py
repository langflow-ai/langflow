"""Actual SDK bucket, application export and execution-preservation checks."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

pytest.importorskip("opentelemetry.sdk.metrics")
from lfx.observability import EVENT_LOOP_LAG_BUCKETS_SECONDS, ApplicationOnlyMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricExportResult
from opentelemetry.sdk.resources import Resource

from lfx import observability_phase as phase


@pytest.fixture
def capture(monkeypatch):
    reader = InMemoryMetricReader()
    provider = MeterProvider(resource=Resource({}), metric_readers=[reader])
    monkeypatch.setattr(phase.metrics, "get_meter", provider.get_meter)
    phase._instruments.cache_clear()
    yield reader
    phase._instruments.cache_clear()
    provider.shutdown()


def points(reader):
    data = reader.get_metrics_data()
    if not data:
        return []
    return [
        (s.scope.name, m.name, p)
        for r in data.resource_metrics
        for s in r.scope_metrics
        for m in s.metrics
        for p in m.data.data_points
    ]


def point(reader, metric):
    selected = [p for _, name, p in points(reader) if name == metric]
    assert len(selected) == 1
    return selected[0]


def clocks(monkeypatch, wall, cpu=None):
    clock = iter(v for duration in wall for v in (0.0, duration))
    monkeypatch.setattr(phase, "perf_counter", lambda: next(clock))
    if cpu is not None:
        clock_cpu = iter(v for duration in cpu for v in (0.0, duration))
        monkeypatch.setattr(phase, "thread_time", lambda: next(clock_cpu))


def bucket_for(bounds, value):
    return next((i for i, upper in enumerate(bounds) if value <= upper), len(bounds))


def test_real_sdk_wall_histogram_separates_subsecond_regions(capture, monkeypatch):
    durations = [0.0002, 0.003, 0.02, 0.2, 2.0, 20.0]
    clocks(monkeypatch, durations)
    for _ in durations:
        with phase.measure_phase(phase.Phase.PREPARE):
            pass
    p = point(capture, "langflow.agent.phase.duration")
    assert tuple(p.explicit_bounds) == phase.WALL_BUCKETS_SECONDS
    assert set(EVENT_LOOP_LAG_BUCKETS_SECONDS) <= set(p.explicit_bounds)
    assert p.count == len(durations)
    assert p.sum == pytest.approx(sum(durations))
    positions = [bucket_for(p.explicit_bounds, v) for v in durations]
    assert len(set(positions)) == len(durations)
    assert all(p.bucket_counts[i] == 1 for i in positions)
    assert p.bucket_counts[-1] == 0


def test_real_sdk_thread_cpu_histogram_has_micro_and_millisecond_coverage(capture, monkeypatch):
    durations = [0.00002, 0.0003, 0.004, 0.08]
    clocks(monkeypatch, [0.001] * len(durations), durations)
    for _ in durations:
        with phase.measure_sync_phase(phase.Phase.AGENT_SETUP):
            pass
    p = point(capture, "langflow.agent.phase.thread_cpu")
    assert tuple(p.explicit_bounds) == phase.THREAD_CPU_BUCKETS_SECONDS
    assert p.count == len(durations)
    assert p.sum == pytest.approx(sum(durations))
    positions = [bucket_for(p.explicit_bounds, v) for v in durations]
    assert len(set(positions)) == len(durations)
    assert all(p.bucket_counts[i] == 1 for i in positions)


def test_application_export_preserves_seconds_bounds_and_fixed_attributes(capture):
    with phase.measure_phase(phase.Phase.FINAL_SEND):
        pass
    forwarded = []
    exporter = SimpleNamespace(
        _preferred_temporality=None,
        _preferred_aggregation=None,
        export=lambda data, *_a, **_k: forwarded.append(data) or MetricExportResult.SUCCESS,
    )
    assert ApplicationOnlyMetricExporter(exporter).export(capture.get_metrics_data()) is MetricExportResult.SUCCESS
    assert len(forwarded) == 1
    for resource in forwarded[0].resource_metrics:
        for scope in resource.scope_metrics:
            assert scope.scope.name == "langflow"
            for metric in scope.metrics:
                assert metric.unit == "s"
                for p in metric.data.data_points:
                    assert set(p.attributes) == {"phase", "outcome"}
                    assert tuple(p.explicit_bounds) == phase.WALL_BUCKETS_SECONDS


def test_handled_error_and_pause_require_explicit_closed_outcomes(capture):
    with phase.measure_phase(phase.Phase.PREPARE) as result:
        try:
            sentinel = "PROMPT-SENTINEL https://private.example/secret"
            raise ValueError(sentinel)
        except ValueError:
            result.error()
            output = {"error": "handled"}
    with phase.measure_phase(phase.Phase.AGENT_EXECUTE) as result:
        result.interrupted()
    assert output == {"error": "handled"}
    emitted = points(capture)
    assert {p.attributes["outcome"] for _, _, p in emitted} == {"error", "interrupted"}
    assert all(set(p.attributes) == {"phase", "outcome"} for _, _, p in emitted)
    assert "PROMPT-SENTINEL" not in str([p.attributes for _, _, p in emitted])


@pytest.mark.asyncio
async def test_wall_cancel_propagates_without_cpu_record(capture):
    entered = asyncio.Event()

    async def work():
        with phase.measure_phase(phase.Phase.AGENT_EXECUTE):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(work())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    emitted = points(capture)
    assert len(emitted) == 1
    assert emitted[0][1] == "langflow.agent.phase.duration"
    assert emitted[0][2].attributes["outcome"] == "cancelled"


def test_explicit_sync_cancel_preserves_cancel_classification(capture):
    with pytest.raises(asyncio.CancelledError), phase.measure_sync_phase(phase.Phase.AGENT_SETUP):
        raise asyncio.CancelledError
    assert {p.attributes["outcome"] for _, _, p in points(capture)} == {"cancelled"}


def test_no_stream_observer_candidate_and_no_component_attached_instruments(capture):
    assert not hasattr(phase, "observe_terminal_send")
    for _ in range(3):
        namespace = {"measure_phase": phase.measure_phase, "Phase": phase.Phase}
        exec(  # noqa: S102 - compile a fixed synthetic component, never user code
            "class SavedComponent:\n def build(self):\n  with measure_phase(Phase.PREPARE):\n   return 42\n", namespace
        )
        instance = namespace["SavedComponent"]()
        assert deepcopy(instance).build() == 42
        assert vars(instance) == {}
    assert point(capture, "langflow.agent.phase.duration").count == 3


def test_recorder_failure_cannot_replace_original_result_or_error(monkeypatch):
    monkeypatch.setattr(phase, "_instruments", lambda: (_ for _ in ()).throw(RuntimeError("recorder failed")))
    with phase.measure_phase(phase.Phase.FINAL_SEND):
        output = 42
    assert output == 42
    original = ValueError("actual operation")
    with pytest.raises(ValueError, match="actual operation") as caught, phase.measure_phase(phase.Phase.FINAL_SEND):
        raise original
    assert caught.value is original


def test_unhashable_private_outcome_is_dropped_without_altering_body(capture):
    with phase.measure_phase(phase.Phase.PREPARE) as result:
        result._outcome = []
        output = 42
    assert output == 42
    assert points(capture) == []


@pytest.mark.parametrize("phase_name", ["private-url", "prepare", object()])
def test_invalid_phase_is_not_a_label(capture, phase_name):
    with pytest.raises(TypeError), phase.measure_phase(phase_name):
        pass
    assert points(capture) == []


def test_thread_cpu_remains_limited_to_setup(capture):
    with (
        pytest.raises(ValueError, match="thread CPU is restricted"),
        phase.measure_sync_phase(phase.Phase.MODEL_CLIENT),
    ):
        pass
    assert points(capture) == []


def test_missing_optional_sdk_preserves_operation(monkeypatch):
    phase._instruments.cache_clear()
    monkeypatch.setattr(phase, "metrics", None)
    try:
        with phase.measure_phase(phase.Phase.PREPARE):
            output = 42
        assert output == 42
        assert phase._instruments() is None
    finally:
        phase._instruments.cache_clear()
