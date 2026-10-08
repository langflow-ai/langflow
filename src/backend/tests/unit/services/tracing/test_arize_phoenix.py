import asyncio
import uuid

import pytest
from langflow.services.tracing.arize_phoenix import ArizePhoenixTracer
from lfx.schema.data import Data

PROJECT_NAME = "openinference.project.name"
SPAN_KIND = "openinference.span.kind"


@pytest.fixture
def tracer():
    return ArizePhoenixTracer.__new__(ArizePhoenixTracer)


def test_data_dict_conversion(tracer):
    value = Data(data={"a": 1, "b": "x"})

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {"a": 1, "b": "x"}


def test_data_list_conversion(tracer):
    value = Data.model_construct(data=[1, Data(data={"x": 2})], text_key="text", default_value="")

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == [1, {"x": 2}]


def test_data_text_payload_preserved(tracer):
    value = Data(data={"text": "hello"})

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {"text": "hello"}


def test_data_nested_structure(tracer):
    value = Data(data={"nested": [1, Data(data={"x": float("inf")})]})

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {"nested": [1, {"x": "NaN"}]}


def test_data_none(tracer):
    value = Data(data=None)

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {}


def test_dict_recursive_conversion(tracer):
    value = {
        "a": Data(data={"b": 1}),
        "c": [Data(data={"text": "text"}), 2],
    }

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == {
        "a": {"b": 1},
        "c": [{"text": "text"}, 2],
    }


def test_list_recursive_conversion(tracer):
    value = [
        Data(data={"x": 1}),
        Data(data={"text": "y"}),
    ]

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == [{"x": 1}, {"text": "y"}]


def test_float_nan_conversion(tracer):
    value = float("nan")

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == "NaN"


def test_float_inf_conversion(tracer):
    value = float("inf")

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == "NaN"


def test_none_type_conversion(tracer):
    value = None

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == "None"


def test_generator_conversion(tracer):
    def gen():
        yield 1

    value = gen()

    result = tracer._convert_to_arize_phoenix_type(value)

    assert isinstance(result, str)


def test_plain_dict_unchanged(tracer):
    value = {"a": 1, "b": 2}

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == value


def test_plain_list_unchanged(tracer):
    value = [1, 2, 3]

    result = tracer._convert_to_arize_phoenix_type(value)

    assert result == value


class _NoopHTTPInstrumentationManager:
    """Keeps the process-global HTTP instrumentors out of span-routing tests."""

    def enable(self, *_args, **_kwargs) -> None:
        """No-op stand-in for enabling HTTP instrumentation."""

    def disable(self, *_args, **_kwargs) -> None:
        """No-op stand-in for disabling HTTP instrumentation."""


@pytest.fixture
def _stub_http_instrumentation(monkeypatch):
    """Replace the process-global HTTP instrumentors with a no-op manager."""
    from langflow.services.tracing import http_instrumentation

    monkeypatch.setattr(
        http_instrumentation,
        "get_http_instrumentation_manager",
        _NoopHTTPInstrumentationManager,
    )


@pytest.fixture
def _phoenix_local_env(monkeypatch):
    """Point the tracer at a local Phoenix endpoint with no API key or batching."""
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    monkeypatch.setenv("ARIZE_PHOENIX_BATCH", "false")
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    monkeypatch.delenv("ARIZE_API_KEY", raising=False)
    monkeypatch.delenv("ARIZE_SPACE_ID", raising=False)


def _spans_by_project(exporters):
    """Map each Phoenix project to its exported spans as ``{span name: span kind}``."""
    spans_by_project: dict[str | None, dict[str, str]] = {}
    for exporter in exporters:
        for span in exporter.get_finished_spans():
            project = span.resource.attributes.get(PROJECT_NAME)
            spans_by_project.setdefault(project, {})[span.name] = span.attributes.get(SPAN_KIND)
    return spans_by_project


@pytest.mark.usefixtures("_stub_http_instrumentation", "_phoenix_local_env")
async def test_langchain_spans_stay_isolated_across_concurrent_workflows(monkeypatch):
    """Regression test for langflow-ai/langflow#15555.

    Each workflow owns a provider bound to a distinct Phoenix project. The two workflows
    overlap: workflow A tears its tracer down while workflow B is still mid-flight, after
    which workflow B emits a tool span and a chain span. Every span must land under its own
    workflow's project instead of a single process-global provider.
    """
    pytest.importorskip("langchain_core")
    pytest.importorskip("openinference.instrumentation.langchain")
    import phoenix.otel as phoenix_otel
    from langchain_core.runnables import RunnableLambda
    from langchain_core.tools import tool
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporters = []

    def _in_memory_exporter(**_kwargs):
        """Exporter stub that captures spans in memory instead of shipping them to Phoenix."""
        exporter = InMemorySpanExporter()
        exporters.append(exporter)
        return exporter

    monkeypatch.setattr(phoenix_otel, "HTTPSpanExporter", _in_memory_exporter)

    def _make_tracer(project_name):
        """Build an ArizePhoenixTracer bound to ``project_name``."""
        return ArizePhoenixTracer(
            trace_name=f"{project_name} - flow-id",
            trace_type="chain",
            project_name=project_name,
            trace_id=uuid.uuid4(),
        )

    tracer_a = _make_tracer("workflow-a")
    tracer_b = _make_tracer("workflow-b")
    assert tracer_a.ready
    assert tracer_b.ready

    handler_a = tracer_a.get_langchain_callback()
    handler_b = tracer_b.get_langchain_callback()
    assert handler_a is not None
    assert handler_b is not None
    assert handler_a is not handler_b

    b_started = asyncio.Event()
    a_ended = asyncio.Event()

    @tool
    async def read_record(project: str) -> str:
        """Return a fixture marker; workflow B blocks here until workflow A tears down."""
        if project == "workflow-b":
            b_started.set()
            await a_ended.wait()
        return project

    async def _body_a(value):
        """Hold workflow A's chain open until workflow B has started."""
        await b_started.wait()
        return value

    async def _run_a():
        """Run workflow A, then tear its tracer down while workflow B is mid-flight."""
        await RunnableLambda(_body_a, name="chain-a").ainvoke("a", config={"callbacks": [handler_a]})
        await read_record.ainvoke({"project": "workflow-a"}, config={"callbacks": [handler_a]})
        tracer_a.end({}, {})
        tracer_a.close()
        a_ended.set()

    async def _run_b():
        """Run workflow B: a tool span before workflow A ends, a chain span after."""
        await read_record.ainvoke({"project": "workflow-b"}, config={"callbacks": [handler_b]})
        await RunnableLambda(lambda value: value, name="chain-b-after-a-end").ainvoke(
            "b", config={"callbacks": [handler_b]}
        )
        tracer_b.end({}, {})
        tracer_b.close()

    await asyncio.wait_for(asyncio.gather(_run_a(), _run_b()), timeout=60)

    spans_by_project = _spans_by_project(exporters)
    assert spans_by_project["workflow-a"]["chain-a"] == "CHAIN"
    assert spans_by_project["workflow-a"]["read_record"] == "TOOL"
    # Workflow B's tool span is emitted after workflow A tears its tracer down.
    assert spans_by_project["workflow-b"]["read_record"] == "TOOL"
    assert spans_by_project["workflow-b"]["chain-b-after-a-end"] == "CHAIN"
    assert "chain-b-after-a-end" not in spans_by_project.get("workflow-a", {})
    assert "chain-a" not in spans_by_project.get("workflow-b", {})
