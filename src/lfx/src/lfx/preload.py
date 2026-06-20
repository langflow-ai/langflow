"""Warm up core component imports and execution paths for snapshot capture.

lfx loads components lazily, so a fresh interpreter pays a large one-time cost on the
first flow build *and* the first run. Pre-warming triggers that cost up front in a
long-lived process — e.g. a Firecracker "golden snapshot" captured before any tenant
flow runs — so the first build/run after restore is cheap, with no loss of isolation.

Two halves, neither performing observable execution:

* **Imports** — importing the core component *classes* (not just their packages) pulls
  in their heavy submodules and dependencies, warming the build path. The model and
  agent components are imported but **never invoked**, so no network call happens.
* **Warm-up run** — running one model-free hermetic flow (ChatInput -> Prompt ->
  ChatOutput) once warms the graph execution machinery. It does in-memory string work
  only: no network, no external side effects.
"""

from __future__ import annotations

import gc
import importlib
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Core components as (module, class) pairs, assumed from standard usage. This list
# can and should evolve if we want to warm more or less components.
# Importing the class (not just the package) is what loads the heavy submodule + deps.
DEFAULT_CORE_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("lfx.components.input_output", "ChatInput"),
    ("lfx.components.input_output", "ChatOutput"),
    ("lfx.components.models_and_agents", "PromptComponent"),
    ("lfx.components.models_and_agents", "LanguageModelComponent"),
    ("lfx.components.models_and_agents", "AgentComponent"),
    ("lfx.components.models_and_agents", "MemoryComponent"),
    ("lfx.components.processing", "ParserComponent"),
    ("lfx.components.utilities", "CalculatorComponent"),
)


class PrewarmError(RuntimeError):
    """Raised when a required core component fails to import, or fork-safety teardown fails."""


@dataclass
class PrewarmResult:
    """Outcome of a :func:`prewarm_core_imports` call."""

    imported: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    warmup_ran: bool = False
    froze: bool = False
    services_torn_down: bool = False
    elapsed_s: float = 0.0


@dataclass
class FlowPrewarmResult:
    """Outcome of a :func:`prewarm_flow` call."""

    built: bool = False
    ran: bool = False
    froze: bool = False
    services_torn_down: bool = False
    elapsed_s: float = 0.0
    error: str | None = None
    # Fork-hostile state left behind by a `run` (empty unless `run=True`). Non-empty here
    # means the warm-up is NOT safe to fork/snapshot as-is.
    ghost_threads: list[str] = field(default_factory=list)
    ghost_connections: list[str] = field(default_factory=list)


def freeze_heap() -> None:
    """Collect, then freeze the heap so GC stops scanning it (preserves CoW sharing)."""
    gc.collect()
    gc.freeze()


def teardown_warm_services() -> None:
    """Dispose every service instantiated during warming, before a fork/snapshot.

    Warming triggers lazy service discovery + instantiation (settings, tracing, and
    anything a registered ``lfx.services`` plugin replaces). The bundled lfx services are
    fork-safe no-ops, but a real plugin (a DB pool, an external cache socket, a telemetry
    thread) opened in ``__init__`` would be inherited live by every process forked from
    this one (Gunicorn ``--preload``). This tears those down — mirroring Langflow's
    ``engine.dispose()`` / cache ``teardown()`` before its master fork.

    A teardown failure is fatal: it raises :class:`PrewarmError` rather than let a
    half-disposed process be captured into a fork. Do NOT call this on the Firecracker
    ``--unsafe-run`` path, where live connections across snapshot/restore are intentional.

    Note: the warm-up runs flows in throwaway ``asyncio.run`` loops, so teardown happens
    in a *new* loop here. A plugin service that binds an async resource to the loop it was
    created on (e.g. an asyncpg pool) may fail to dispose cross-loop; that surfaces as a
    fatal :class:`PrewarmError` (fail-safe — the process is refused for fork rather than
    captured dirty), never silent corruption. Bundled lfx service teardowns are loop-free.
    """
    import asyncio

    from lfx.services.manager import get_service_manager

    try:
        asyncio.run(get_service_manager().teardown(raise_on_error=True))
    except Exception as exc:
        msg = f"service teardown before fork/snapshot failed: {exc}"
        raise PrewarmError(msg) from exc


def _component_key(module: str, attr: str) -> str:
    return f"{module}:{attr}"


def _run_hermetic_warmup() -> None:
    """Build and run one model-free flow to warm the execution machinery.

    Uses only in-memory components (ChatInput -> Prompt -> ChatOutput). No model, no
    network, no external side effects. Must be called without a running event loop.
    """
    import asyncio

    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.components.models_and_agents import PromptComponent
    from lfx.graph.graph.base import Graph

    chat_input = ChatInput(_id="prewarm_chat_input")
    prompt = PromptComponent(_id="prewarm_prompt")
    prompt.set(template="{warmup}", warmup=chat_input.message_response)
    chat_output = ChatOutput(_id="prewarm_chat_output")
    chat_output.set(input_value=prompt.build_prompt)

    graph = Graph(chat_input, chat_output)
    graph.prepare()

    async def _run() -> None:
        async for _ in graph.async_start(inputs={"input_value": "prewarm"}):
            pass

    asyncio.run(_run())


def prewarm_core_imports(
    components: Sequence[tuple[str, str]] | None = None,
    *,
    required: Sequence[tuple[str, str]] | None = None,
    warmup_run: bool = True,
    freeze: bool = False,
    teardown_services: bool = True,
) -> PrewarmResult:
    """Warm core component imports (and optionally the execution machinery).

    Args:
        components: ``(module, class)`` pairs to import. Defaults to
            :data:`DEFAULT_CORE_COMPONENTS`.
        required: Components whose import failure is fatal (raises :class:`PrewarmError`).
            Defaults to whichever requested components are part of the default core set;
            anything else that fails is reported in ``result.failed`` instead.
        warmup_run: When true (default), run one model-free hermetic flow to warm the
            graph execution machinery. In-memory only — no network, no side effects.
        freeze: When true, run ``gc.collect()`` then ``gc.freeze()`` after warming, taking
            the warmed objects out of GC's scan set to preserve copy-on-write sharing
            across VMs restored from the same snapshot.
        teardown_services: When true (default), dispose any services instantiated during
            warming (see :func:`teardown_warm_services`) so the process is fork-safe. A
            teardown failure raises :class:`PrewarmError`. Set false to keep warmed live
            service instances (Firecracker snapshot, which tolerates live state).

    Returns:
        A :class:`PrewarmResult` describing what imported, what failed, whether the
        warm-up run executed, and the elapsed time.
    """
    requested = tuple(components) if components is not None else DEFAULT_CORE_COMPONENTS
    required_set = set(required) if required is not None else (set(DEFAULT_CORE_COMPONENTS) & set(requested))

    result = PrewarmResult()
    start = time.perf_counter()
    for module, attr in requested:
        try:
            getattr(importlib.import_module(module), attr)
        except Exception as exc:  # report optional failures, re-raise required ones
            if (module, attr) in required_set:
                msg = f"required core component {_component_key(module, attr)!r} failed to import: {exc}"
                raise PrewarmError(msg) from exc
            result.failed[_component_key(module, attr)] = f"{type(exc).__name__}: {exc}"
        else:
            result.imported.append(_component_key(module, attr))

    if warmup_run:
        _run_hermetic_warmup()
        result.warmup_ran = True

    # Dispose warmed service instances BEFORE freezing, so a fork-hostile plugin service
    # is not captured into a preload fork (and gc.collect during freeze can reclaim them).
    if teardown_services:
        teardown_warm_services()
        result.services_torn_down = True

    if freeze:
        freeze_heap()
        result.froze = True

    result.elapsed_s = time.perf_counter() - start
    return result


def _run_flow_once(graph, input_value: str) -> None:
    """Execute a built graph once. Must be called without a running event loop."""
    import asyncio

    async def _run() -> None:
        async for _ in graph.async_start(inputs={"input_value": input_value}):
            pass

    asyncio.run(_run())


def prewarm_flow(
    flow,
    *,
    run: bool = False,
    input_value: str = "prewarm",
    freeze: bool = False,
    teardown_services: bool = True,
) -> FlowPrewarmResult:
    """Warm a specific flow by building it, and optionally running it end-to-end.

    Because the flow is static, this warms exactly the components it uses — no
    component allow-list, no importing the world.

    Args:
        flow: Flow JSON as a path, string, or dict (anything ``load_flow_from_json`` accepts).
        run: When true, **fully executes** the flow (``async_start``) for maximum warmth.
            This fires the flow's **real side effects** (model calls, writes, etc.), so the
            caller must supply any required credentials and ensure the flow is idempotent.
            When false, only the build path is warmed (no execution, no side effects).
        input_value: Input passed to the flow when ``run`` is true.
        freeze: When true, freeze the heap after warming (see :func:`freeze_heap`).
        teardown_services: When true (default), dispose services instantiated while building
            so the process stays fork-safe (raises :class:`PrewarmError` on teardown failure).
            Ignored when ``run`` is true — that path intentionally leaks live connections for
            Firecracker snapshot/restore, so tearing services down would defeat it.

    Returns:
        A :class:`FlowPrewarmResult`. Load/build/run failures are captured in ``error``
        rather than raised, so callers warming many flows are not aborted by one bad flow.
    """
    from lfx.load import load_flow_from_json

    result = FlowPrewarmResult()
    start = time.perf_counter()
    graph = None
    try:
        graph = load_flow_from_json(flow, disable_logs=True)
        graph.prepare()
        result.built = True
        if run:
            _run_flow_once(graph, input_value)
            result.ran = True
    except Exception as exc:  # noqa: BLE001 - capture so multi-flow warming isn't aborted by one failure
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        # Drop the flow's component instances and run their finalizers now, so any
        # per-instance clients/connections opened during `run` are closed before a
        # subsequent freeze/fork. Import/class/JIT warmth lives in modules, not instances,
        # so it is unaffected. (Live execution before fork is still unsafe — see docs;
        # this is hygiene, not a substitute for a fork-safe warm path.)
        graph = None  # explicit drop of the only ref before gc
        gc.collect()
        if run:
            # A run can open connections/threads; report what (if anything) survived so the
            # caller can refuse to fork/snapshot a dirty process.
            from lfx.fork import fork_safety_report

            report = fork_safety_report()
            result.ghost_threads = report.ghost_threads
            result.ghost_connections = report.ghost_connections

    # Build-only (fork-safe) path: dispose services opened during the build before freezing.
    # A `run` deliberately keeps live state (Firecracker), so never tear down there.
    # Capture a teardown failure into ``error`` instead of raising: this function's contract
    # is that one bad flow never aborts a multi-flow warming loop, so teardown — which raises
    # PrewarmError — must be funneled into ``error`` like load/build/run failures above.
    if teardown_services and not run and result.error is None:
        try:
            teardown_warm_services()
            result.services_torn_down = True
        except PrewarmError as exc:
            result.error = str(exc)

    if freeze:
        freeze_heap()
        result.froze = True

    result.elapsed_s = time.perf_counter() - start
    return result
