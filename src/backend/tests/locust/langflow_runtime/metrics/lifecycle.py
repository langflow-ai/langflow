"""Locust lifecycle event helpers for composite duration tracking."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator


class LifecycleRecord:
    """Mutable record yielded by ``lifecycle_timer`` for optional metadata."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._start = time.perf_counter()
        self.exception: BaseException | None = None
        self.response_length = 0

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000


def fire_lifecycle(
    name: str,
    response_time_ms: float,
    exception: BaseException | None = None,
    response_length: int = 0,
) -> None:
    """Fire a Locust request event for a composite lifecycle duration."""
    from locust import events

    events.request.fire(
        request_type="LIFECYCLE",
        name=name,
        response_time=response_time_ms,
        response_length=response_length,
        exception=exception,
    )


@contextmanager
def lifecycle_timer(name: str) -> Generator[LifecycleRecord, None, None]:
    """Time a composite lifecycle block and fire success/failure on exit."""
    record = LifecycleRecord(name)
    try:
        yield record
    except BaseException as exc:
        record.exception = exc
        fire_lifecycle(name, record.elapsed_ms, exc, record.response_length)
        raise
    else:
        fire_lifecycle(name, record.elapsed_ms, None, record.response_length)
