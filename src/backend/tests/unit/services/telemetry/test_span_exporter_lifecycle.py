"""In-process span fixtures must leave the worker's shared provider usable."""

import importlib
import logging

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.mark.parametrize(
    ("module_name", "provider_exists"),
    [
        ("tests.unit.api.test_build_flow_span", False),
        ("tests.unit.services.telemetry.test_protocol_sweep", False),
        ("tests.unit.services.telemetry.test_protocol_sweep", True),
        ("tests.unit.services.telemetry.test_queued_trace_continuity", False),
        ("tests.unit.services.telemetry.test_queued_trace_continuity", True),
    ],
)
def test_span_fixture_teardown_preserves_later_spans(module_name, provider_exists, monkeypatch, caplog):
    """Later spans stay quiet, reach other exporters, and do not refill the retired exporter."""
    fixture = importlib.import_module(module_name).span_exporter
    provider = TracerProvider() if provider_exists else None

    def install_provider(value):
        nonlocal provider
        assert provider is None
        provider = value

    monkeypatch.setattr(trace, "get_tracer_provider", lambda: provider)
    monkeypatch.setattr(trace, "set_tracer_provider", install_provider)
    lifecycle = fixture.__wrapped__()
    exporter = next(lifecycle)
    observer = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(observer))
    tracer = provider.get_tracer("test.fixture.lifecycle")
    try:
        tracer.start_span("during-fixture").end()
        assert [span.name for span in exporter.get_finished_spans()] == ["during-fixture"]
        assert next(lifecycle, None) is None

        with caplog.at_level(logging.WARNING):
            tracer.start_span("after-fixture").end()

        assert not caplog.records
        assert exporter.get_finished_spans() == ()
        assert [span.name for span in observer.get_finished_spans()] == ["during-fixture", "after-fixture"]
    finally:
        provider.shutdown()
