"""Webhook subscribe-before-POST lifecycle client."""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field
from typing import Any

from tests.locust.langflow_runtime.clients.base import (
    ApiClient,
    ApplicationError,
    LocustTransport,
    close_response,
    iter_response_lines,
)
from tests.locust.langflow_runtime.clients.sse import SseDeadlines, SseEvent, parse_sse_events

try:
    import gevent
    from gevent.event import Event as GeventEvent
except ImportError:  # pragma: no cover
    gevent = None
    GeventEvent = None


@dataclass(frozen=True)
class WebhookCopy:
    flow_id: str
    endpoint_name: str


@dataclass
class WebhookResult:
    accepted: bool
    completed: bool
    accept_status: int | None = None
    frames: list[SseEvent] = field(default_factory=list)
    error: str | None = None
    accept_elapsed_s: float | None = None
    complete_elapsed_s: float | None = None


@dataclass(frozen=True)
class WebhookCorrelation:
    connected: bool
    accepted: bool
    completed: bool
    terminal_event: str | None = None


def correlate_webhook_events(events: list[SseEvent], *, accepted: bool = False) -> WebhookCorrelation:
    """Classify webhook SSE progression for unit tests and metrics."""
    connected = any(event.event == "connected" for event in events)
    completed = any(event.event == "end" for event in events)
    terminal = next((event.event for event in reversed(events) if event.event in {"end", "error"}), None)
    return WebhookCorrelation(
        connected=connected,
        accepted=accepted,
        completed=completed,
        terminal_event=terminal,
    )


class WebhookCopyPool:
    """Lease provisioned webhook flow copies (one in-flight POST per copy)."""

    def __init__(self, copies: list[WebhookCopy]) -> None:
        self._available: queue.Queue[WebhookCopy] = queue.Queue()
        for copy in copies:
            self._available.put(copy)
        self._in_use: set[WebhookCopy] = set()

    def lease(self, *, timeout_s: float | None = None) -> WebhookCopy:
        try:
            copy = self._available.get(timeout=timeout_s)
        except queue.Empty as exc:
            msg = "no webhook copy available to lease"
            raise ApplicationError(msg) from exc
        self._in_use.add(copy)
        return copy

    def release(self, copy: WebhookCopy) -> None:
        if copy in self._in_use:
            self._in_use.discard(copy)
            self._available.put(copy)

    def release_all(self) -> None:
        """Return every leased copy to the available pool."""
        for copy in list(self._in_use):
            self.release(copy)


class WebhooksClient:
    """Subscribe to webhook-events SSE, POST webhook, correlate ``end``."""

    def __init__(
        self,
        *,
        api: ApiClient,
        workload: str = "webhook",
        flow_class: str = "passthrough",
        pool: WebhookCopyPool | None = None,
    ) -> None:
        self.api = api
        self.api_key = api.api_key or ""
        self.workload = workload
        self.flow_class = flow_class
        self.pool = pool

    def _tx(self, operation: str) -> str:
        return ApiClient.tx_name("webhook", operation, self.workload, self.flow_class)

    def subscribe_post_complete(
        self, copy: WebhookCopy, payload: dict[str, Any], *, timeout_s: float = 60.0
    ) -> WebhookResult:
        started = time.monotonic()

        # gevent is installed with Locust even in ordinary CLI processes, but
        # plain httpx I/O is not monkey-patched there. Using greenlets with an
        # HttpxTransport blocks the gevent hub in the SSE reader, so the webhook
        # POST cannot run until the read deadline expires. Greenlets are only
        # appropriate for the Locust transport; live provision/preflight uses
        # real threads around the thread-safe httpx client.
        if isinstance(self.api.transport, LocustTransport) and gevent is not None and GeventEvent is not None:
            return self._subscribe_post_complete_gevent(copy, payload, timeout_s=timeout_s, started=started)

        return self._subscribe_post_complete_threaded(copy, payload, timeout_s=timeout_s, started=started)

    def _subscribe_post_complete_gevent(
        self,
        copy: WebhookCopy,
        payload: dict[str, Any],
        *,
        timeout_s: float,
        started: float,
    ) -> WebhookResult:
        assert gevent is not None
        assert GeventEvent is not None
        frames: list[SseEvent] = []
        connected = GeventEvent()
        ended = GeventEvent()
        errors: list[str] = []
        accept_status: list[int] = []

        def listen() -> None:
            sse_url = f"/api/v1/webhook-events/{copy.flow_id}"
            response = None
            try:
                response = self.api.request(
                    "GET",
                    sse_url,
                    name=self._tx("sse_subscribe"),
                    headers={"Accept": "text/event-stream"},
                    stream=True,
                    timeout=timeout_s,
                )
                status = int(getattr(response, "status_code", getattr(response, "status", 0)))
                if status != 200:
                    errors.append(f"SSE HTTP {status}")
                    ended.set()
                    return
                for event in parse_sse_events(
                    iter_response_lines(response),
                    deadlines=SseDeadlines(connect_s=timeout_s, read_s=timeout_s, idle_s=timeout_s),
                    terminal_events={"end", "error"},
                ):
                    frames.append(event)
                    if event.event == "connected":
                        connected.set()
                    if event.event in {"end", "error"}:
                        ended.set()
                        return
                errors.append("SSE stream ended without terminal event")
                ended.set()
            except Exception as exc:
                errors.append(str(exc))
                ended.set()
            finally:
                if response is not None:
                    close_response(response)

        def post_when_ready() -> None:
            if not connected.wait(timeout=timeout_s):
                errors.append("timed out waiting for connected event")
                ended.set()
                return
            try:
                response = self.api.request(
                    "POST",
                    f"/api/v1/webhook/{copy.endpoint_name}",
                    name=self._tx("post_accept"),
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=timeout_s,
                )
                status = int(getattr(response, "status_code", getattr(response, "status", 0)))
                accept_status.append(status)
                if status != 202:
                    errors.append(f"webhook POST HTTP {status}")
                    ended.set()
            except Exception as exc:
                errors.append(str(exc))
                ended.set()

        listener = gevent.spawn(listen)
        poster = gevent.spawn(post_when_ready)
        ended.wait(timeout=timeout_s)
        listener.kill()
        poster.kill()

        accept_elapsed = time.monotonic() - started
        correlation = correlate_webhook_events(frames, accepted=bool(accept_status and accept_status[0] == 202))
        return WebhookResult(
            accepted=correlation.accepted,
            completed=correlation.completed,
            accept_status=accept_status[0] if accept_status else None,
            frames=frames,
            error=errors[0] if errors else None,
            accept_elapsed_s=accept_elapsed,
            complete_elapsed_s=time.monotonic() - started if correlation.completed else None,
        )

    def _subscribe_post_complete_threaded(
        self,
        copy: WebhookCopy,
        payload: dict[str, Any],
        *,
        timeout_s: float,
        started: float,
    ) -> WebhookResult:
        import threading

        frames: list[SseEvent] = []
        frames_lock = threading.Lock()
        connected = threading.Event()
        ended = threading.Event()
        errors: list[str] = []
        accept_status: list[int] = []

        def listen() -> None:
            sse_url = f"/api/v1/webhook-events/{copy.flow_id}"
            response = None
            try:
                response = self.api.request(
                    "GET",
                    sse_url,
                    name=self._tx("sse_subscribe"),
                    headers={"Accept": "text/event-stream"},
                    stream=True,
                    timeout=timeout_s,
                )
                status = int(getattr(response, "status_code", getattr(response, "status", 0)))
                if status != 200:
                    errors.append(f"SSE HTTP {status}")
                    ended.set()
                    return
                for event in parse_sse_events(
                    iter_response_lines(response),
                    deadlines=SseDeadlines(connect_s=timeout_s, read_s=timeout_s, idle_s=timeout_s),
                    terminal_events={"end", "error"},
                ):
                    with frames_lock:
                        frames.append(event)
                    if event.event == "connected":
                        connected.set()
                    if event.event in {"end", "error"}:
                        ended.set()
                        return
                errors.append("SSE stream ended without terminal event")
                ended.set()
            except Exception as exc:
                errors.append(str(exc))
                ended.set()
            finally:
                if response is not None:
                    close_response(response)

        def post_when_ready() -> None:
            if not connected.wait(timeout=timeout_s):
                errors.append("timed out waiting for connected event")
                ended.set()
                return
            try:
                response = self.api.request(
                    "POST",
                    f"/api/v1/webhook/{copy.endpoint_name}",
                    name=self._tx("post_accept"),
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=timeout_s,
                )
                status = int(getattr(response, "status_code", getattr(response, "status", 0)))
                accept_status.append(status)
                if status != 202:
                    errors.append(f"webhook POST HTTP {status}")
                    ended.set()
            except Exception as exc:
                errors.append(str(exc))
                ended.set()

        listener = threading.Thread(target=listen, daemon=True)
        poster = threading.Thread(target=post_when_ready, daemon=True)
        listener.start()
        poster.start()
        ended.wait(timeout=timeout_s)
        listener.join(timeout=1.0)
        poster.join(timeout=1.0)

        correlation = correlate_webhook_events(frames, accepted=bool(accept_status and accept_status[0] == 202))
        return WebhookResult(
            accepted=correlation.accepted,
            completed=correlation.completed,
            accept_status=accept_status[0] if accept_status else None,
            frames=frames,
            error=errors[0] if errors else None,
            accept_elapsed_s=time.monotonic() - started,
            complete_elapsed_s=time.monotonic() - started if correlation.completed else None,
        )

    def run_with_pool(self, payload: dict[str, Any], *, timeout_s: float = 60.0) -> WebhookResult:
        if self.pool is None:
            raise ApplicationError("WebhookCopyPool is not configured")
        copy = self.pool.lease()
        try:
            return self.subscribe_post_complete(copy, payload, timeout_s=timeout_s)
        finally:
            self.pool.release(copy)
