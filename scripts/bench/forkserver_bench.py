#!/usr/bin/env python
"""Forkserver + prewarm cold-start harness — models the PLANNED wxo TRM path.

TRM already forks a fresh process per Langflow tool call (``mp.Process``,
``forkserver`` start method on Linux). Today the child cold-spawns a nested
``lfx run`` subprocess, paying the full lfx import on *every* call. The plan:
preload the forkserver control process with prewarmed + frozen lfx
(``lfx.preload``) and run the flow IN-PROCESS in the fork child, so each call
inherits warm lfx via copy-on-write with no per-call import.

Three paths map to the three rows of the cost table:

  * ``cold`` here, run in the BAKED image -> "baked image, nested lfx run"
            intermediate (~1.8-2 s no-LLM, ~3.5-4 s model). Child cold-spawns
            ``python -m lfx run``.
  * ``warm`` here -> the end-state fix: forkserver preloaded with
            ``_lfx_prewarm_shim`` (prewarm + freeze), child runs in-process
            (~0.2-0.5 s no-LLM, ~1.5-2 s model / LLM-bound).
  * "current PVC nested subprocess" (~30 s) is the status quo this replaces.

THE signal that proves COW is working is a **no-LLM flow** (input->output): warm
per-call should drop to sub-half-second. A model flow hides the import win behind
the ~1.5 s OpenAI call, so success and partial-failure look alike there.

MUST run INSIDE the Linux container. On a macOS host, forkserver may crash or not
reflect Linux CoW, and the default start method is ``spawn`` (no fork, no COW) ->
the child re-imports and you see a false negative. The podman image is Linux, so:

    C=$(podman run -d --rm -e OPENAI_API_KEY lfx-coldstart:bench)
    podman exec -w /app/data $C python forkserver_bench.py cold        inputoutput.json "hi" 10
    podman exec -w /app/data $C python forkserver_bench.py warm        inputoutput.json "hi" 10
    # --- load-testing passes (all WARM / the fix) -------------------------------
    podman exec -w /app/data $C python forkserver_bench.py concurrency inputoutput.json "hi" 8
    podman exec -w /app/data $C python forkserver_bench.py sustained   inputoutput.json "hi" 200
    podman exec -w /app/data $C python forkserver_bench.py ramp        inputoutput.json "hi" 16
    podman stop $C

Modes:
  * cold/warm   sequential per-call latency (the original A/B).
  * concurrency fork N children AT ONCE, hold them alive, sample the whole tree's
                memory -> COW sharing (total Pss vs N x warm-base RSS), throughput,
                and per-call latency under contention. n = concurrency level.
  * sustained   n sequential calls; track the forkserver CONTROL-proc RSS first->
                last (leak signal: warm base should stay flat) + latency p50/p95/p99.
  * ramp        sweep concurrency 1,2,4,... up to n; per level report throughput,
                p50/p95 latency, and total tree Pss -> capacity / saturation curve.

Heavier flows (bigger graph + a CPU-bound CustomComponent + Agents that call out):
    # graph-size / memory only (BUILD, no execution -> no OpenAI, free, deterministic):
    podman exec -e BENCH_BUILD_ONLY=1 -w /app/data $C \
        python forkserver_bench.py concurrency agentcpuflow.json     "hi" 8
    podman exec -e BENCH_BUILD_ONLY=1 -w /app/data $C \
        python forkserver_bench.py concurrency agentcpuflowmore.json "hi" 8   # 25-node, ~20 extra components
    # full run (Agents make REAL OpenAI calls + the ~3 s CPU burn -> CPU saturation under load):
    podman exec -e OPENAI_API_KEY -w /app/data $C \
        python forkserver_bench.py ramp agentcpuflow.json "do the task" 8

Env toggles:
  * BENCH_BUILD_ONLY=1  stop after graph BUILD (no async_start) -> measure build +
    per-child memory with NO execution: no Agent/LLM calls, no network, no cost.
    Use for the agent flows' graph-size/memory comparison; drop it to run for real.
  * BENCH_PREWARM_FLOW=/app/data/flow.json  warm that flow's BUILD path (agent/
    langchain imports the core prewarm misses) -- pass via ``podman exec -e``.
  * BENCH_NO_FREEZE=1   skip gc.freeze() to A/B per-child private-dirty memory.
  * BENCH_GLOBAL_VARS='{"x-langflow-global-var-foo":"bar"}'  exercise TRM's
    request-scoped global-var injection in the warm child.
  * BENCH_WAVES=3       concurrency-mode: how many waves at the given level.
  * BENCH_HOLD_TIMEOUT=120  seconds a child holds (alive) for the memory sample.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

_EXPECTED_ARGC = 5  # prog + mode + flow + utterance + n
_SMAP_KEYS = ("Rss", "Pss", "Shared_Clean", "Shared_Dirty", "Private_Clean", "Private_Dirty")


def _smaps(pid: int | str = "self") -> dict[str, int]:
    """Read selected /proc/<pid>/smaps_rollup counters (kB), Linux only.

    Pss (proportional set size) splits shared pages across sharers, so summing
    Pss over {control proc + all live children} == total physical RAM the warm
    tree occupies — the honest "did CoW actually share lfx" number. Private_Dirty
    is the per-child copied-after-fork cost (the freeze signal).
    """
    out: dict[str, int] = {}
    try:
        with Path(f"/proc/{pid}/smaps_rollup").open() as fh:
            for line in fh:
                key = line.split(":", 1)[0]
                if key in _SMAP_KEYS:
                    out[key] = int(line.split()[1])
    except (OSError, ValueError):
        return {}
    return out


def _private_dirty_kb() -> int | None:
    """Resident *private* (copied-after-fork) memory of this process, Linux only."""
    return _smaps("self").get("Private_Dirty")


def _pct(xs: list[float], p: float) -> float:
    """Linear-interpolated percentile; nan on empty."""
    if not xs:
        return float("nan")
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def _run_flow_in_process(flow_path: str, utterance: str, global_vars: dict) -> None:
    """The in-process execution ``run_langflow_tool_sync`` becomes (scope R3).

    BENCH_BUILD_ONLY=1 stops after the graph BUILD (load + apply vars) and skips
    async_start. That isolates build cost + per-child memory for the graph-size
    comparison (e.g. agentcpuflow 5-node vs agentcpuflowmore 25-node) with NO
    execution -> no Agent/LLM calls, no network, no API cost, no rate limits. Use
    it for the agent flows so the concurrency/memory numbers measure the graph,
    not OpenAI. Drop it to run the whole flow (Agents call out; the CustomComponent
    burns its ~3 s of CPU -> the real CPU-saturation-under-concurrency test).
    """
    from lfx.load import load_flow_from_json

    graph = load_flow_from_json(flow_path, disable_logs=True)
    if global_vars:
        from lfx.cli.runtime_variables import apply_global_vars_to_graph

        apply_global_vars_to_graph(graph, global_vars)

    if os.environ.get("BENCH_BUILD_ONLY"):
        return  # build + memory only; no execution

    import asyncio

    from lfx.schema.schema import InputValueRequest

    async def _run() -> None:
        async for _ in graph.async_start(inputs=InputValueRequest(input_value=utterance)):
            pass

    asyncio.run(_run())


def _child_warm(flow_path: str, utterance: str, global_vars: dict, q) -> None:
    """In-process execution — what ``run_langflow_tool_sync`` becomes (scope R3)."""
    _run_flow_in_process(flow_path, utterance, global_vars)
    q.put({"priv_dirty_kb": _private_dirty_kb()})


def _child_cold(flow_path: str, utterance: str, _global_vars: dict, q) -> None:
    """Nested cold ``lfx run`` subprocess — what TRM does today (baseline)."""
    subprocess.run(  # noqa: S603 -- fixed argv, no shell, benchmark harness
        [sys.executable, "-m", "lfx", "run", flow_path, utterance, "-f", "text"],
        check=True,
        capture_output=True,
    )
    q.put({"priv_dirty_kb": None})


def _child_concurrent(flow_path: str, utterance: str, global_vars: dict, ready_q, release_evt) -> None:
    """Warm in-process call that REPORTS then HOLDS, so the parent can sample the
    whole tree's memory while every sibling is still resident."""
    t0 = time.perf_counter()
    ok, err = True, ""
    try:
        _run_flow_in_process(flow_path, utterance, global_vars)
    except Exception as exc:  # noqa: BLE001 -- record, don't abort the wave
        ok, err = False, f"{type(exc).__name__}: {exc}"
    dt = time.perf_counter() - t0
    ready_q.put(
        {
            "pid": os.getpid(),
            "compute_s": dt,
            "ok": ok,
            "err": err,
            "self": _smaps("self"),
            "ctrl": _smaps(os.getppid()),  # forkserver control proc = shared warm base
        }
    )
    release_evt.wait(timeout=int(os.environ.get("BENCH_HOLD_TIMEOUT", "120")))


def _noop(q) -> None:
    q.put({"priv_dirty_kb": None})


def _warm_boot(ctx) -> None:
    """Register the prewarm preload and force the control proc to start NOW, so
    timed loops measure steady state, not the one-time forkserver boot."""
    ctx.set_forkserver_preload(["_lfx_prewarm_shim"])
    q = ctx.Queue()
    t0 = time.perf_counter()
    p = ctx.Process(target=_noop, args=(q,))
    p.start()
    q.get(timeout=600)
    p.join()
    print(f"[boot] forkserver spawn + prewarm + freeze: {time.perf_counter() - t0:.3f}s", flush=True)


def _wave(ctx, args: tuple, c: int) -> tuple[list[dict], float]:
    """Fork *c* warm children at once; return their reports + wall-to-all-ready.

    Children hold (alive) after reporting, so when this returns every child in
    *reports* is still resident — the caller samples memory, then we release+join.
    """
    ready_q = ctx.Queue()
    release = ctx.Event()
    procs = []
    t0 = time.perf_counter()
    for _ in range(c):
        p = ctx.Process(target=_child_concurrent, args=(*args, ready_q, release))
        p.start()
        procs.append(p)
    reports: list[dict] = []
    for _ in range(c):
        try:
            reports.append(ready_q.get(timeout=int(os.environ.get("BENCH_HOLD_TIMEOUT", "120"))))
        except Exception:  # noqa: BLE001 -- a stuck child shouldn't hang the whole run
            break
    wall = time.perf_counter() - t0  # all c finished COMPUTE (now holding)
    release.set()
    for p in procs:
        p.join(timeout=30)
        if p.is_alive():
            p.terminate()
            p.join()
    return reports, wall


def _mb(kb: int) -> str:
    return f"{kb / 1024:.0f}MB"


def run_concurrency(ctx, flow: str, utt: str, gv: dict, c: int) -> None:
    waves = int(os.environ.get("BENCH_WAVES", "3"))
    print(f"== CONCURRENCY: {c} warm children at once, {waves} wave(s) ==", flush=True)
    for w in range(waves):
        reports, wall = _wave(ctx, (flow, utt, gv), c)
        got = len(reports)
        comp = [r["compute_s"] for r in reports]
        fails = [r for r in reports if not r.get("ok", True)]
        ctrl_rss = reports[0]["ctrl"].get("Rss", 0) if reports else 0
        ctrl_pss = reports[0]["ctrl"].get("Pss", 0) if reports else 0
        priv = [r["self"].get("Private_Dirty", 0) for r in reports]
        total_pss = ctrl_pss + sum(r["self"].get("Pss", 0) for r in reports)
        naive = c * ctrl_rss  # what c independent cold processes would cost (no sharing)
        saving = (1 - total_pss / naive) * 100 if naive else float("nan")
        print(
            f"[wave {w}] got={got}/{c} fail={len(fails)}  "
            f"throughput={got / wall:.1f} calls/s  wall={wall:.3f}s  "
            f"compute p50={_pct(comp, 50):.3f}s p95={_pct(comp, 95):.3f}s",
            flush=True,
        )
        print(
            f"[wave {w}] mem: warm-base(ctrl) Rss={_mb(ctrl_rss)}  "
            f"per-child Private_Dirty mean={statistics.fmean(priv) / 1024:.0f}MB max={max(priv) / 1024:.0f}MB  "
            f"TOTAL tree Pss={_mb(total_pss)}  vs no-share {_mb(naive)} -> {saving:.0f}% saved by CoW",
            flush=True,
        )
        if fails:
            print(f"[wave {w}] first error: {fails[0]['err']}", file=sys.stderr, flush=True)


def run_sustained(ctx, flow: str, utt: str, gv: dict, n: int) -> None:
    print(f"== SUSTAINED: {n} sequential warm calls (leak watch on warm base) ==", flush=True)
    comp: list[float] = []
    ctrl_rss: list[int] = []
    priv: list[int] = []
    step = max(1, n // 10)
    for i in range(n):
        reports, _ = _wave(ctx, (flow, utt, gv), 1)
        if not reports:
            print(f"[sustained] call {i}: NO REPORT", file=sys.stderr, flush=True)
            continue
        r = reports[0]
        comp.append(r["compute_s"])
        if r["ctrl"].get("Rss"):
            ctrl_rss.append(r["ctrl"]["Rss"])
        if r["self"].get("Private_Dirty"):
            priv.append(r["self"]["Private_Dirty"])
        if i % step == 0:
            print(f"[sustained] {i}/{n}  call={r['compute_s']:.3f}s  ctrl_rss={_mb(r['ctrl'].get('Rss', 0))}", flush=True)
    if comp:
        print(
            f"\n[sustained] latency n={len(comp)}  "
            f"p50={_pct(comp, 50):.3f}s p95={_pct(comp, 95):.3f}s p99={_pct(comp, 99):.3f}s max={max(comp):.3f}s"
        )
    if ctrl_rss:
        delta = ctrl_rss[-1] - ctrl_rss[0]
        print(
            f"[sustained] warm-base ctrl Rss: first={_mb(ctrl_rss[0])} last={_mb(ctrl_rss[-1])} "
            f"delta={delta / 1024:+.1f}MB  <- should be ~flat; steady growth == leak in the warm parent"
        )
    if priv:
        print(f"[sustained] per-child Private_Dirty: first={_mb(priv[0])} last={_mb(priv[-1])} mean={_mb(int(statistics.fmean(priv)))}")


def run_ramp(ctx, flow: str, utt: str, gv: dict, max_c: int) -> None:
    levels: list[int] = []
    c = 1
    while c <= max_c:
        levels.append(c)
        c *= 2
    if levels[-1] != max_c:
        levels.append(max_c)
    print(f"== RAMP: concurrency sweep {levels} (capacity / saturation curve) ==", flush=True)
    print(f"{'C':>4}  {'thr/s':>7}  {'p50':>7}  {'p95':>7}  {'tot_Pss':>8}  {'fail':>4}", flush=True)
    for level in levels:
        reports, wall = _wave(ctx, (flow, utt, gv), level)
        got = len(reports)
        comp = [r["compute_s"] for r in reports]
        fails = sum(1 for r in reports if not r.get("ok", True))
        ctrl_pss = reports[0]["ctrl"].get("Pss", 0) if reports else 0
        total_pss = ctrl_pss + sum(r["self"].get("Pss", 0) for r in reports)
        print(
            f"{level:>4}  {got / wall:>7.1f}  {_pct(comp, 50):>6.3f}s  {_pct(comp, 95):>6.3f}s  "
            f"{_mb(total_pss):>8}  {fails:>4}",
            flush=True,
        )


def main() -> int:
    if len(sys.argv) != _EXPECTED_ARGC:
        print(
            "usage: forkserver_bench.py <cold|warm|concurrency|sustained|ramp> <flow.json> <utterance> <n>",
            file=sys.stderr,
        )
        return 2

    mode, flow_path, utterance, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    global_vars = json.loads(os.environ.get("BENCH_GLOBAL_VARS") or "{}")

    ctx = mp.get_context("forkserver")
    print(f"[bench] platform={sys.platform} start_method={ctx.get_start_method()} mode={mode}", flush=True)
    if sys.platform == "darwin":
        print(
            "[bench] WARNING: macOS host -- forkserver may crash or not reflect Linux CoW. "
            "Run INSIDE the Linux container for valid numbers.",
            file=sys.stderr,
            flush=True,
        )

    # Load-testing passes are all WARM (they validate the fix at scale).
    if mode in ("concurrency", "sustained", "ramp"):
        _warm_boot(ctx)
        if mode == "concurrency":
            run_concurrency(ctx, flow_path, utterance, global_vars, n)
        elif mode == "sustained":
            run_sustained(ctx, flow_path, utterance, global_vars, n)
        else:
            run_ramp(ctx, flow_path, utterance, global_vars, n)
        return 0

    # Original sequential cold/warm A/B.
    target = _child_warm if mode == "warm" else _child_cold
    if mode == "warm":
        ctx.set_forkserver_preload(["_lfx_prewarm_shim"])
        q = ctx.Queue()
        t0 = time.perf_counter()
        p = ctx.Process(target=_noop, args=(q,))
        p.start()
        q.get(timeout=600)
        p.join()
        print(f"[warm] BOOT (forkserver spawn + prewarm + freeze): {time.perf_counter() - t0:.3f}s", flush=True)

    samples: list[float] = []
    priv: list[int] = []
    for i in range(n):
        q = ctx.Queue()
        t0 = time.perf_counter()
        p = ctx.Process(target=target, args=(flow_path, utterance, global_vars, q))
        p.start()
        try:
            res = q.get(timeout=120)
        except Exception:  # noqa: BLE001 -- a hung/erroring call shouldn't abort the run
            p.terminate()
            p.join()
            print(f"[{mode}] call {i}: TIMEOUT/ERROR", file=sys.stderr)
            continue
        p.join()
        dt = time.perf_counter() - t0
        samples.append(dt)
        pd = (res or {}).get("priv_dirty_kb")
        if pd is not None:
            priv.append(pd)
        print(f"[{mode}] call {i}: {dt:.3f}s" + (f"  priv_dirty={pd}kB" if pd is not None else ""), flush=True)

    if samples:
        print(
            f"\n[{mode}] per-call  n={len(samples)}  "
            f"min={min(samples):.3f}s  median={statistics.median(samples):.3f}s  "
            f"mean={statistics.fmean(samples):.3f}s  max={max(samples):.3f}s  "
            f"p95={_pct(samples, 95):.3f}s"
        )
    if priv:
        print(
            f"[{mode}] per-child Private_Dirty  mean={statistics.fmean(priv):.0f}kB  "
            f"max={max(priv)}kB  (compare with BENCH_NO_FREEZE=1 to see the freeze effect)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
