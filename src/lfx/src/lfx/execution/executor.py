"""Executor abstract base class.

An ``Executor`` is the pluggable backend that turns a ``Unit`` into a stream of
``StepResult`` events terminated by a single ``RunComplete``. The ``Coordinator``
holds at most one instance per ``kind`` and dispatches every ``run()`` against it,
so implementations must observe the lifecycle contract documented below.

Authoring a new executor:

1. Subclass ``Executor`` and set ``kind`` to a unique, stable string.
2. Implement ``execute`` as an ``async def`` generator. Yield zero or more
   ``StepResult`` items, then exactly one ``RunComplete``.
3. Register through one of three paths (all equivalent at runtime):
   - Explicit: ``get_service(ServiceType.EXECUTOR_SERVICE).register(MyExecutor())``
   - Plugin: ``[project.entry-points."lfx.executors"] my_kind = "pkg.mod:MyExecutor"``
   - Service replacement: ``@register_service(ServiceType.EXECUTOR_SERVICE)``
4. Validate with the shared contract suite: subclass
   ``tests.unit.execution.test_executor_contract.ExecutorContract`` in your tests
   and provide the two fixtures. All universal seam guarantees are checked there.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.execution.types import RunComplete, StepResult, Unit


class Executor(ABC):
    """Pluggable execution backend for the seam.

    Class attributes:
        kind: Unique stable identifier used by ``ExecutorRegistry`` and by
            ``settings.executor_kind``. Two executors with the same ``kind`` cannot
            coexist in a single registry; entry-point discovery refuses collisions.

    Lifecycle contract:
        - A single instance is shared across all runs of its ``kind``. The same
          instance may receive concurrent ``execute()`` calls (e.g. parallel API
          requests, ``Loop`` subgraphs). Implementations MUST be safe under
          concurrent calls and MUST NOT carry per-run state on ``self``.
        - ``execute()`` is called once per ``Unit``. Each call MUST return a fresh
          async iterator; reusing/caching a generator across calls is a bug.
        - The stream MUST emit zero or more ``StepResult`` followed by exactly one
          terminal ``RunComplete``. ``Coordinator.run_to_completion`` raises if the
          terminal item is missing.
        - Exceptions raised inside the generator propagate to the consumer. The
          generator's finalizer runs as usual, so any ``async with`` / cleanup code
          will execute. Consumers MAY drop the iterator mid-stream (``aclose``);
          implementations MUST tolerate this without hanging or leaking external
          resources (subprocesses, sockets, locks, file handles).
        - ``execute()`` MUST be tolerant of arbitrary keys in ``unit.runtime_options``:
          ignore keys the executor doesn't recognize. Keys prefixed with ``_`` are
          reserved for executor-internal flags; non-owning executors must ignore them.
    """

    kind: ClassVar[str]

    @abstractmethod
    def execute(self, unit: Unit) -> AsyncIterator[StepResult | RunComplete]:
        """Run ``unit`` and yield the seam-typed event stream.

        Args:
            unit: The work item. ``unit.graph`` is executor-defined (an in-memory
                ``Graph`` for in-process; whatever shape a remote/sandboxed executor
                expects). ``unit.inputs`` and ``unit.runtime_options`` carry per-run
                state.

        Yields:
            ``StepResult`` items for mid-run events (executor-defined payloads),
            terminated by exactly one ``RunComplete``.
        """
