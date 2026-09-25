"""Domain-level application tracing with no OpenTelemetry leakage into business code.

This module is the only place that knows application span names, semantic attributes,
span kinds, queue links, or the safe error policy.  Callers describe domain operations;
the lower-level :mod:`lfx.observability` module owns providers and export filtering.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import inspect
import json
import time
from importlib.resources import files
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from lfx import observability as _otel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

    from opentelemetry.trace import Span

try:
    from opentelemetry import trace
    from opentelemetry.context import Context
    from opentelemetry.trace import Link, SpanKind
except ImportError:  # pragma: no cover - exercised in a subprocess without the extra
    trace = None
    Context = None
    Link = None
    SpanKind = None

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")

AUTH_SPAN = "langflow.request.auth"
FLOW_LOAD_SPAN = "langflow.flow.load"
LEGACY_FLOW_EXECUTION_SPAN = "flow.execute"
GRAPH_EXECUTION_SPAN = "langflow.graph.execute"
VERTEX_EXECUTION_SPAN = "langflow.vertex.execute"
RESPONSE_SERIALIZE_SPAN = "langflow.response.serialize"
STREAM_SEND_SPAN = "langflow.stream.send"
JOB_ENQUEUE_SPAN = "langflow.job.enqueue"
JOB_DEQUEUE_SPAN = "langflow.job.dequeue"
JOB_QUEUE_WAIT_SPAN = "langflow.job.queue_wait"
JOB_EXECUTE_SPAN = "langflow.job.execute"

UNKNOWN_COMPONENT_TYPE = "custom_or_unknown"
_component_types: frozenset[str] | None = None


def _known_component_types() -> frozenset[str]:
    """Return component names from the immutable bundled registry.

    A workflow controls ``vertex_type``.  Only names shipped in Langflow's bundled
    component index are safe metric dimensions; extensions and arbitrary payload values
    collapse to one token.
    """
    global _component_types  # noqa: PLW0603
    if _component_types is not None:
        return _component_types
    known: set[str] = set()
    try:
        index_path = files("lfx").joinpath("_assets/component_index.json")
        index = json.loads(index_path.read_text(encoding="utf-8"))
        entries = index.get("entries", [])
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, list):
                    continue
                try:
                    _category, components = entry
                except ValueError:
                    continue
                if isinstance(components, dict):
                    known.update(str(name) for name in components)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    # Interface vertices are runtime primitives and are not guaranteed to live in
    # every generated component-index variant.
    known.update({"ChatInput", "ChatOutput", "DataOutput", "TextInput", "TextOutput", "WebhookInput"})
    _component_types = frozenset(known)
    return _component_types


def canonical_component_type(value: object) -> str:
    """Map a workflow-provided component type to a bounded registry value."""
    candidate = str(value)
    return candidate if candidate in _known_component_types() else UNKNOWN_COMPONENT_TYPE


def observe_auth(surface: str) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Trace an authentication dependency without changing its body or signature."""

    def decorator(operation: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(operation)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            with _otel.application_span(
                AUTH_SPAN,
                {"langflow.phase": "request.auth", "langflow.auth.surface": surface},
            ):
                return await operation(*args, **kwargs)

        return wrapped

    return decorator


def observe_flow_load(operation: Callable[P, R]) -> Callable[P, R]:
    """Trace graph construction while preserving the decorated signature."""
    signature = inspect.signature(operation)

    @functools.wraps(operation)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        bound = signature.bind_partial(*args, **kwargs)
        instantiate = bound.arguments.get("instantiate_components", True)
        with _otel.application_span(
            FLOW_LOAD_SPAN,
            {
                "langflow.phase": "flow.load",
                "langflow.flow.load.source": "payload",
                "langflow.flow.instantiate_components": bool(instantiate),
            },
        ) as span:
            graph = operation(*args, **kwargs)
            span.set_attribute("langflow.graph.vertex_count", len(getattr(graph, "vertices", ())))
            span.set_attribute("langflow.graph.edge_count", len(getattr(graph, "edges", ())))
            return graph

    return wrapped


def observe_vertex_execution(operation: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Trace one vertex build with a bounded, registry-backed component type."""
    signature = inspect.signature(operation)

    @functools.wraps(operation)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        bound = signature.bind_partial(*args, **kwargs)
        graph = bound.arguments.get("self")
        vertex_id = bound.arguments.get("vertex_id")
        vertex = graph.get_vertex(vertex_id)
        attributes = {
            "langflow.phase": "vertex.execute",
            "langflow.vertex.kind": type(vertex).__name__,
            "langflow.vertex.is_loop": bool(vertex.is_loop),
        }
        with _otel.application_span(VERTEX_EXECUTION_SPAN, attributes) as span:
            if span.is_recording():
                span.set_attribute("langflow.component.type", canonical_component_type(vertex.vertex_type))
            return await operation(*args, **kwargs)

    return wrapped


def observe_response_serialization(operation: Callable[P, R]) -> Callable[P, R]:
    """Trace conversion of an execution result into the public response model."""

    @functools.wraps(operation)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        protocol = _otel.get_execution_protocol()
        attributes: dict[str, Any] = {"langflow.phase": "response.serialize"}
        if protocol is not None:
            attributes["protocol"] = protocol
        with _otel.application_span(RESPONSE_SERIALIZE_SPAN, attributes):
            return operation(*args, **kwargs)

    return wrapped


async def observe_stream_send(
    source: AsyncIterator[T],
    *,
    protocol: str,
    stream_protocol: str,
    kind: str,
    frame_selector: Callable[[T], bytes] | None = None,
) -> AsyncIterator[T | bytes]:
    """Yield a stream under one detached span and record only bounded counts."""
    with _otel.detached_application_span(
        STREAM_SEND_SPAN,
        {
            "protocol": protocol,
            "langflow.phase": "stream.send",
            "langflow.stream.protocol": stream_protocol,
            "langflow.stream.kind": kind,
        },
    ) as span:
        frame_count = 0
        byte_count = 0
        try:
            async for item in source:
                frame = frame_selector(item) if frame_selector is not None else item
                frame_count += 1
                byte_count += len(frame)  # type: ignore[arg-type]
                yield frame if frame_selector is not None else item
        finally:
            span.set_attribute("langflow.stream.frame_count", frame_count)
            span.set_attribute("langflow.stream.byte_count", byte_count)


async def observe_job_enqueue(
    operation: Awaitable[R],
    *,
    job_id: str,
    backend: str,
) -> R:
    """Run a job publication under producer semantics."""
    attributes = _job_attributes(job_id, backend)
    attributes.update({"messaging.operation.type": "send", "langflow.phase": "job.enqueue"})
    kind = SpanKind.PRODUCER if SpanKind is not None else None
    with _otel.application_span(JOB_ENQUEUE_SPAN, attributes, kind=kind):
        return await operation


async def observe_in_process_job_enqueue(
    job_id: str,
    operation: Callable[[], Awaitable[None]],
    publish: Callable[[Callable[[], Awaitable[None]]], Awaitable[None]],
) -> None:
    """Publish in-process work and capture its consumer link inside the producer span."""
    attributes = _job_attributes(job_id, "in_process")
    attributes.update({"messaging.operation.type": "send", "langflow.phase": "job.enqueue"})
    kind = SpanKind.PRODUCER if SpanKind is not None else None
    with _otel.application_span(JOB_ENQUEUE_SPAN, attributes, kind=kind):
        await publish(observe_queued_job(job_id, operation))


def _job_attributes(job_id: str, backend: str) -> dict[str, Any]:
    return {
        "messaging.system": "langflow",
        "messaging.destination.name": "workflow.jobs",
        "langflow.job.id": job_id,
        "langflow.job.type": "workflow",
        "langflow.job.backend": backend,
    }


def observe_queued_job(
    job_id: str,
    operation: Callable[[], Awaitable[None]],
    *,
    backend: str = "in_process",
) -> Callable[[], Awaitable[None]]:
    """Wrap queued work so the executor remains unaware of tracing mechanics."""
    enqueued_at = time.time_ns()
    origin = None
    if trace is not None:
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            origin = span_context

    @functools.wraps(operation)
    async def observed() -> None:
        links = [Link(origin)] if origin is not None and Link is not None else None
        base = _job_attributes(job_id, backend)
        with _otel.application_span(
            JOB_QUEUE_WAIT_SPAN,
            {**base, "messaging.operation.type": "settle", "langflow.phase": "job.queue_wait"},
            links=links,
            root=True,
            start_time=enqueued_at,
        ):
            pass
        consumer_kind = SpanKind.CONSUMER if SpanKind is not None else None
        with _otel.application_span(
            JOB_DEQUEUE_SPAN,
            {**base, "messaging.operation.type": "receive", "langflow.phase": "job.dequeue"},
            kind=consumer_kind,
            links=links,
            root=True,
        ):
            pass
        with _otel.application_span(
            JOB_EXECUTE_SPAN,
            {
                **base,
                "messaging.operation.type": "process",
                "langflow.phase": "job.execute",
            },
            kind=consumer_kind,
            links=links,
            root=True,
        ) as scope:
            try:
                await operation()
            except asyncio.CancelledError:
                scope.set_attribute("langflow.job.status", "cancelled")
                raise

    return observed


class GraphExecutionObservation:
    """Marks failures swallowed by a graph driver without exposing span objects."""

    __slots__ = ("error_type",)

    def __init__(self) -> None:
        self.error_type: str | None = None

    def record_error(self, error_type: str) -> None:
        self.error_type = error_type


def application_span_missing_current() -> bool:
    """Whether installed tracing lacks the current span a delegated run promised."""
    return trace is not None and not trace.get_current_span().is_recording()


def _start_graph_spans(*, make_current: bool) -> tuple[Span, Span, contextlib.ExitStack]:
    tracer = trace.get_tracer(_otel.APPLICATION_TRACER_NAME)
    parent = trace.get_current_span()
    parent_context = parent.get_span_context()
    queued_link = _otel.get_queued_trace_link()
    if queued_link is not None and not parent.is_recording():
        flow_span = tracer.start_span(LEGACY_FLOW_EXECUTION_SPAN, context=Context(), links=[queued_link])
    elif parent_context.is_valid and not parent.is_recording():
        flow_span = tracer.start_span(
            LEGACY_FLOW_EXECUTION_SPAN,
            context=Context(),
            links=[Link(parent_context)],
        )
    else:
        flow_span = tracer.start_span(LEGACY_FLOW_EXECUTION_SPAN)
    graph_span = tracer.start_span(GRAPH_EXECUTION_SPAN, context=trace.set_span_in_context(flow_span))
    flow_span.set_attribute("langflow.phase", "flow.execute")
    graph_span.set_attribute("langflow.phase", "graph.execute")
    stack = contextlib.ExitStack()
    if make_current:
        stack.enter_context(
            trace.use_span(flow_span, end_on_exit=False, record_exception=False, set_status_on_exception=False)
        )
        stack.enter_context(
            trace.use_span(graph_span, end_on_exit=False, record_exception=False, set_status_on_exception=False)
        )
    return flow_span, graph_span, stack


def _set_safe_error(span: Span, error_type: str) -> None:
    span.set_status(trace.Status(trace.StatusCode.ERROR, error_type))
    span.set_attribute("error.type", error_type)
    span.add_event("exception", {"exception.type": error_type})


@contextlib.contextmanager
def observe_graph_execution(
    *,
    is_subgraph: bool,
    make_current: bool,
    identifiers: Callable[[], dict[str, str | None]],
    paused_exception: type[BaseException],
) -> Iterator[GraphExecutionObservation]:
    """Own the legacy flow span and its graph child outside graph business logic."""
    observation = GraphExecutionObservation()
    if trace is None or is_subgraph:
        yield observation
        return
    flow_span, graph_span, stack = _start_graph_spans(make_current=make_current)
    status = "ok"
    try:
        with stack:
            yield observation
    except paused_exception:
        status = "paused"
        raise
    except asyncio.CancelledError:
        status = "cancelled"
        raise
    except Exception as exc:
        status = "error"
        error_type = _otel.root_error_type(exc)
        _set_safe_error(flow_span, error_type)
        _set_safe_error(graph_span, error_type)
        raise
    finally:
        if status == "ok" and observation.error_type is not None:
            status = "error"
            _set_safe_error(flow_span, observation.error_type)
            _set_safe_error(graph_span, observation.error_type)
        attributes = identifiers()
        protocol = _otel.get_execution_protocol()
        client = _otel.get_execution_client()
        for span in (flow_span, graph_span):
            for key, value in attributes.items():
                if value:
                    span.set_attribute(key, value)
            if protocol is not None:
                span.set_attribute("protocol", protocol)
            if client is not None:
                span.set_attribute("client", client)
            span.set_attribute("status", status)
        graph_span.end()
        flow_span.end()
