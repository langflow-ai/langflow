"""The carrier that lets a queued run point back at the request that queued it.

A background run happens after its request has returned, in a worker that may be a different
process. ``contextvars`` do not survive that, so the trace context has to travel on the job
row. These tests pin the two ends of that trip and, as much as they pin the happy path, the
cases where the answer is honestly nothing.

The failure mode worth guarding against is not a missing link. It is a *fabricated* one: a
carrier that yields a link when no request was ever traced draws a relationship in the
operator's APM that never existed, which is worse than an orphan because it looks real.
"""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk.trace")

from lfx.observability import (
    JOB_TRACE_CARRIER_KEY,
    extract_trace_link,
    get_queued_trace_link,
    inject_trace_carrier,
    queued_trace_link,
)


@pytest.fixture
def tracer():
    """A real SDK tracer. The propagator reads the live context, so a stub would prove nothing."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    yield trace.get_tracer("test.originating.request")
    provider.shutdown()


def test_the_carrier_round_trips_the_trace_id(tracer):
    """The load-bearing case: what the worker extracts is the request's own trace."""
    with tracer.start_as_current_span("originating.request") as span:
        expected = span.get_span_context().trace_id
        carrier = inject_trace_carrier()

    link = extract_trace_link(carrier)

    assert link is not None
    assert link.context.trace_id == expected


def test_the_carrier_round_trips_the_sampling_flag(tracer):
    """The reason this is a traceparent and not a bare trace id.

    A bare id carries no sampling decision, so a linked run could be dropped by a sampler that
    kept the request it came from -- leaving the operator a request with a reference to a run
    that was never exported. The flag is the whole argument for the standard form, so it gets
    its own assertion rather than riding along untested with the trace id.
    """
    with tracer.start_as_current_span("originating.request") as span:
        expected = span.get_span_context().trace_flags
        carrier = inject_trace_carrier()

    link = extract_trace_link(carrier)

    assert link is not None
    assert link.context.trace_flags == expected
    assert link.context.trace_flags.sampled is expected.sampled


def test_existing_metadata_is_preserved(tracer):
    """The carrier shares the job's metadata dict with application keys."""
    with tracer.start_as_current_span("originating.request"):
        carrier = inject_trace_carrier({"request": "keep me", "pre_pause_outputs": [1, 2]})

    assert carrier["request"] == "keep me"
    assert carrier["pre_pause_outputs"] == [1, 2]
    assert JOB_TRACE_CARRIER_KEY in carrier


def test_nothing_is_written_when_nothing_is_tracing():
    """Absent rather than invented, the same rule the protocol attribute follows."""
    carrier = inject_trace_carrier({"request": "keep me"})

    assert JOB_TRACE_CARRIER_KEY not in carrier
    assert carrier == {"request": "keep me"}


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        {"request": "no carrier here"},
        {JOB_TRACE_CARRIER_KEY: ""},
        {JOB_TRACE_CARRIER_KEY: "not-a-traceparent"},
        {JOB_TRACE_CARRIER_KEY: "00-00000000000000000000000000000000-0000000000000000-01"},
        {JOB_TRACE_CARRIER_KEY: 12345},
    ],
)
def test_a_carrier_that_cannot_be_trusted_yields_no_link(metadata):
    """Every one of these must be None rather than a link to something invented.

    The all-zero trace id is in the list deliberately: it parses as well-formed and is the
    value an invalid context serialises to, so a naive implementation returns a link to a
    trace that does not exist.
    """
    assert extract_trace_link(metadata) is None


def test_the_ambient_link_is_unset_by_default():
    """Asserted before the binding test: otherwise that test could pass on a leaked value."""
    assert get_queued_trace_link() is None


def test_the_ambient_link_binds_and_resets(tracer):
    """Reset matters: a worker serves many jobs on one task.

    Without the reset, one job's originating request would stay attached and the next job's
    run would link to the wrong request, which is a fabricated relationship again.
    """
    with tracer.start_as_current_span("originating.request"):
        link = extract_trace_link(inject_trace_carrier())

    assert link is not None
    with queued_trace_link(link):
        assert get_queued_trace_link() is link

    assert get_queued_trace_link() is None


def test_binding_none_is_a_no_op():
    """A synchronous run has no queued link, and must not pay for the machinery."""
    with queued_trace_link(None):
        assert get_queued_trace_link() is None

    assert get_queued_trace_link() is None
