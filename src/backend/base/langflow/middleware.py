import math
import threading
from collections import deque
from dataclasses import dataclass, field
from http import HTTPStatus
from time import perf_counter
from typing import Any

from fastapi import HTTPException
from lfx.log.logger import logger

from langflow.services.deps import get_settings_service

REQUEST_TIMING_SAMPLE_SIZE = 1000


@dataclass
class _RouteTiming:
    count: int = 0
    total_ms: float = 0
    min_ms: float = math.inf
    max_ms: float = 0
    slow_count: int = 0
    error_count: int = 0
    samples_ms: deque[float] = field(default_factory=lambda: deque(maxlen=REQUEST_TIMING_SAMPLE_SIZE))


class RequestTimingRegistry:
    """Keep bounded, per-process request-duration statistics grouped by route template."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._routes: dict[tuple[str, str], _RouteTiming] = {}

    def record(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
        slow_threshold_ms: float,
    ) -> None:
        with self._lock:
            timing = self._routes.setdefault((method, route), _RouteTiming())
            timing.count += 1
            timing.total_ms += duration_ms
            timing.min_ms = min(timing.min_ms, duration_ms)
            timing.max_ms = max(timing.max_ms, duration_ms)
            timing.slow_count += duration_ms >= slow_threshold_ms
            timing.error_count += status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
            timing.samples_ms.append(duration_ms)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            routes = []
            for (method, route), timing in self._routes.items():
                samples = sorted(timing.samples_ms)
                routes.append(
                    {
                        "method": method,
                        "route": route,
                        "count": timing.count,
                        "avg_ms": round(timing.total_ms / timing.count, 2),
                        "min_ms": round(timing.min_ms, 2),
                        "max_ms": round(timing.max_ms, 2),
                        "p50_ms": round(_percentile(samples, 0.50), 2),
                        "p95_ms": round(_percentile(samples, 0.95), 2),
                        "slow_count": timing.slow_count,
                        "error_count": timing.error_count,
                    }
                )
        routes.sort(key=lambda item: item["max_ms"], reverse=True)
        return {
            "process_local": True,
            "sample_size_per_route": REQUEST_TIMING_SAMPLE_SIZE,
            "routes": routes,
        }


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0
    index = min(math.ceil(len(sorted_values) * percentile) - 1, len(sorted_values) - 1)
    return sorted_values[max(index, 0)]


request_timing_registry = RequestTimingRegistry()


class RequestTimingMiddleware:
    """Log HTTP request durations and collect bounded statistics by route template."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings_service().settings
        if not settings.request_timing_enabled:
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        status_code = 500
        recorded = False

        async def record_request() -> None:
            nonlocal recorded
            if recorded:
                return
            recorded = True
            duration_ms = (perf_counter() - started_at) * 1000
            route_object = scope.get("route")
            route = getattr(route_object, "path", None) or scope.get("path", "<unknown>")
            method = scope.get("method", "<unknown>")
            request_timing_registry.record(
                method=method,
                route=route,
                status_code=status_code,
                duration_ms=duration_ms,
                slow_threshold_ms=settings.request_timing_slow_threshold_ms,
            )
            await logger.ainfo(
                "HTTP request completed: method=%s route=%s status=%s duration_ms=%.2f",
                method,
                route,
                status_code,
                duration_ms,
            )

        async def send_with_timing(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                await record_request()

        try:
            await self.app(scope, receive, send_with_timing)
        except Exception:
            await record_request()
            raise


class MaxFileSizeException(HTTPException):
    def __init__(self, detail: str = "File size is larger than the maximum file size {}MB"):
        super().__init__(status_code=413, detail=detail)


# Adapted from https://github.com/steinnes/content-size-limit-asgi/blob/master/content_size_limit_asgi/middleware.py#L26
class ContentSizeLimitMiddleware:
    """Content size limiting middleware for ASGI applications.

    Args:
      app (ASGI application): ASGI application
      max_content_size (optional): the maximum content size allowed in bytes, None for no limit
      exception_cls (optional): the class of exception to raise (ContentSizeExceeded is the default)
    """

    def __init__(
        self,
        app,
    ):
        self.app = app
        self.logger = logger

    @staticmethod
    def receive_wrapper(receive):
        received = 0

        async def inner():
            max_file_size_upload = get_settings_service().settings.max_file_size_upload
            nonlocal received
            message = await receive()
            if message["type"] != "http.request" or max_file_size_upload is None:
                return message
            body_len = len(message.get("body", b""))
            received += body_len
            if received > max_file_size_upload * 1024 * 1024:
                # max_content_size is in bytes, convert to MB
                received_in_mb = round(received / (1024 * 1024), 3)
                msg = (
                    f"Content size limit exceeded. Maximum allowed is {max_file_size_upload}MB"
                    f" and got {received_in_mb}MB."
                )
                raise MaxFileSizeException(msg)
            return message

        return inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        wrapper = self.receive_wrapper(receive)
        await self.app(scope, wrapper, send)
