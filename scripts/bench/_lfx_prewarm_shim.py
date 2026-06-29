"""Forkserver preload shim — runs ONCE in the forkserver control process.

Registered via ``mp.set_forkserver_preload(["_lfx_prewarm_shim"])`` by
``forkserver_bench.py`` (and, in production, by wxo TRM's ``server-lite``).
Importing this module warms lfx and freezes the heap, so every forked child
inherits warm, copy-on-write-shared lfx with **no per-call import**.

This module MUST import lfx and run the prewarm *at import time* — that is the
whole point. ``set_forkserver_preload`` only helps because importing this shim
in the control process executes the warming below; if lfx were imported lazily
in the child instead, there would be no inheritance and no speedup.

Mirrors the ``lfx prewarm`` CLI ordering: warm everything, tear down services
(fork-safety), verify fork-safety, then freeze once at the end.

Env toggles (set on the process that starts the forkserver):
  * BENCH_PREWARM_FLOW=/path/flow.json  also warm that flow's BUILD path (no run,
    no network) so children inherit its components/langchain imports — covers
    what the core prewarm misses for agent/model flows.
  * BENCH_NO_FREEZE=1  skip ``gc.freeze()`` so you can A/B the per-child
    private-dirty memory the freeze is meant to suppress (latency is unaffected).
"""

import os
import sys
import time

import lfx.load  # noqa: F401  -- warm the flow-load path in the control process too
from lfx.preload import (
    freeze_heap,
    prewarm_core_imports,
    prewarm_flow,
    teardown_warm_services,
)

_t0 = time.perf_counter()

# Core component imports + model-free hermetic warm-up run (no freeze/teardown yet).
_core = prewarm_core_imports(warmup_run=True, freeze=False, teardown_services=False)

# Optional: warm a specific flow's BUILD path so the child inherits its
# components/langchain imports. Build-only -> no run, no side effects, no network.
_flow = os.environ.get("BENCH_PREWARM_FLOW")
if _flow:
    prewarm_flow(_flow, run=False, freeze=False, teardown_services=False)

# Dispose warmed services so a child can't inherit a live pool/socket/thread.
teardown_warm_services()

# Fork-safety verification: any live thread/connection left in the control process
# is inherited broken by every fork (child hangs/dies/leaks). Surface it loudly
# BEFORE anyone trusts the latency numbers.
try:
    from lfx.fork import fork_safety_report

    _rep = fork_safety_report()
    if _rep.ghost_threads or _rep.ghost_connections:
        print(
            f"[prewarm-shim] WARNING fork-UNSAFE: threads={_rep.ghost_threads} "
            f"connections={_rep.ghost_connections} -- numbers are NOT trustworthy",
            file=sys.stderr,
            flush=True,
        )
    else:
        print("[prewarm-shim] fork-safety OK (no ghost threads/connections)", file=sys.stderr, flush=True)
except Exception as _exc:  # noqa: BLE001 -- diagnostic only
    print(f"[prewarm-shim] fork_safety_report unavailable: {_exc}", file=sys.stderr, flush=True)

# gc.freeze() preserves CoW across children (stops refcount/GC writes from dirtying
# shared pages). Pure memory win; single-call latency is unaffected by it.
if os.environ.get("BENCH_NO_FREEZE"):
    print("[prewarm-shim] BENCH_NO_FREEZE set -> skipping gc.freeze()", file=sys.stderr, flush=True)
else:
    freeze_heap()

print(
    f"[prewarm-shim] warmed {len(_core.imported)} core component(s)"
    + (f" + flow {_flow}" if _flow else "")
    + f" in {time.perf_counter() - _t0:.3f}s",
    file=sys.stderr,
    flush=True,
)
