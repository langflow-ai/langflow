"""Value objects for the execution layer.

These three dataclasses are the entire vocabulary of the seam: a ``Unit`` flows from
``Coordinator`` into ``Executor.execute()``, which yields a stream of ``StepResult``
items terminated by a single ``RunComplete``. Every consumer downstream of the
coordinator (``run_to_completion``, ``stream``, ``flow_executor``, the CLI, ``Loop``
subgraphs) reads only these types, so changes here ripple widely. Keep them small.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Unit:
    """A self-contained slice of work handed to an ``Executor``.

    Attributes:
        graph: The graph (or graph-shaped object) the executor should run. Executors
            decide what they can accept here -- the in-process executor wants a real
            ``lfx.Graph``; a remote executor may want a serialized form. There is no
            seam-level constraint other than "the executor knows what to do with it."
        inputs: Per-run input dicts. Shape is consumer-defined.
        runtime_options: A free-form bag of run-scoped options. Stringly typed on
            purpose: the seam can't enumerate every option every executor might want
            (event managers, session IDs, fallback flags, executor-specific tokens),
            and pinning a schema here would force every change into this module.
            Conventions worth knowing:

            - Keys starting with ``_`` are reserved for executor-internal flags
              (e.g. ``_use_arun_legacy`` selects the legacy passthrough in the
              in-process executor). Other executors MUST ignore unknown keys.
            - Common keys recognized by the in-process executor:
              ``initial_inputs``, ``max_iterations``, ``config``, ``event_manager``,
              ``reset_output_values``, ``fallback_to_env_vars``, ``session_id``.
            - Other executors are free to define their own keys; document them in
              the executor module.
    """

    graph: Any
    inputs: list[dict[str, Any]] = field(default_factory=list)
    runtime_options: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """A single mid-run event from an executor.

    ``payload`` is intentionally untyped at the seam level. Each executor decides
    what mid-run events look like for its backend:

    - ``InProcessExecutor`` yields ``Vertex`` / ``Finish`` instances from
      ``Graph.async_start``.
    - A remote executor (e.g. stepflow) might yield protobuf status events.
    - A sandboxed executor might yield structured ``StepStarted`` / ``StepCompleted``
      records.

    Consumers that need a uniform shape across executors should normalize at the
    consumer site (or wrap an executor with an adapter), not push a structured event
    type down through the seam. Doing the latter would force every executor to
    translate its native event vocabulary into a synthetic one and would mask
    information the native vocabulary carries.

    ``Coordinator.stream()`` unwraps ``StepResult.payload`` for callers that want a
    raw event stream; ``Coordinator.run()`` yields the full ``StepResult``/``
    RunComplete`` union for callers that want the seam shape.
    """

    payload: Any


@dataclass
class RunComplete:
    """Terminal item in an executor stream.

    ``outputs`` is populated only by executors / paths that have a meaningful notion
    of "final outputs of the run." In particular:

    - The in-process executor's *legacy* path (selected via
      ``runtime_options["_use_arun_legacy"]``) populates ``outputs`` with the
      ``list[RunOutputs]`` returned by ``Graph._arun_legacy``. ``Graph.arun`` reads
      this via ``Coordinator.run_to_completion``.
    - The in-process executor's *streaming* path yields ``RunComplete(outputs=[])``;
      consumers of the streaming path are expected to collect what they need from
      ``StepResult.payload`` events along the way (this is what ``flow_executor``,
      the CLI, ``Loop``, and ``run/base`` already do via ``Coordinator.stream``).
    - Other executors MAY populate ``outputs`` with whatever terminal-status event
      their backend provides (e.g. a stepflow ``RunCompletedEvent``).

    Bottom line: the *only* universal contract on ``outputs`` is that it is a list.
    If you need final values across all executors, collect them from the stream;
    if you specifically need the legacy ``list[RunOutputs]`` shape, use
    ``Coordinator.run_to_completion`` with ``_use_arun_legacy=True`` against the
    in-process executor.
    """

    outputs: list[Any]
