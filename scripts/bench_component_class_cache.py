#!/usr/bin/env python
"""Self-contained A/B benchmark + safety check for caching compiled component classes.

Runs against STOCK langflow -- it installs the cache at runtime for the "cached"
arm, so reviewers do not need to apply the patch first.  Run it on an unpatched
checkout to reproduce the numbers, then again on the patched branch to confirm
the shipped patch behaves identically to the runtime-installed cache.

    uv venv .venv-bench --python 3.12
    VIRTUAL_ENV=.venv-bench uv pip install -e src/lfx
    .venv-bench/bin/python bench_component_class_cache.py
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import functools
import inspect
import json
import os
import statistics
import sys
import time

os.environ.setdefault("LANGFLOW_LOG_LEVEL", "ERROR")

REPEATS = 5  # independent samples per arm; we report the median
INNER = 20  # flow runs per sample


# --------------------------------------------------------------------------
# cache install / uninstall (so one process can measure both arms)
# --------------------------------------------------------------------------
def install_cache() -> None:
    """Install the lru_cache on the eval boundary, mirroring the patch."""
    from lfx.custom import validate
    from lfx.interface.initialize import loading

    # Keyed on ``code`` alone, exactly as the shipped patch is: on a cache hit
    # neither create_class NOR extract_class_name runs, so a hit costs zero
    # ast.parse.  Keying on (code, class_name) instead would re-parse on every
    # call to compute the key, understating the cache and overstating what the
    # parse-dedup adds on top of it.
    @functools.lru_cache(maxsize=512)
    def eval_cached(code: str):
        return validate.create_class(code, validate.extract_class_name(code))

    loading.eval_custom_component_code = eval_cached


def uninstall_cache() -> None:
    """Force the UNCACHED path.

    Deliberately does not restore ``lfx.custom.eval.eval_custom_component_code``:
    on a patched checkout that function already carries the lru_cache, which
    would make the "stock" arm silently measure the cached path.  Rebuilding the
    uncached body here makes the arm correct on patched and unpatched checkouts
    alike.
    """
    from lfx.custom import validate
    from lfx.interface.initialize import loading

    def eval_uncached(code: str):
        return validate.create_class(code, validate.extract_class_name(code))

    loading.eval_custom_component_code = eval_uncached


def install_parse_dedup() -> None:
    """Remove the redundant ast.parse, keeping the uncached compile.

    ``extract_class_name`` parses the RAW source; ``create_class`` parses
    ``DEFAULT_IMPORT_STRING + replaced_source``.  Two different strings, so the
    first module cannot simply be handed to the second -- the workable form is
    the reverse: derive the class name from the augmented parse.  Verified
    equivalent on all component sources in ``_assets/component_index.json``.
    """
    import ast

    from lfx.custom import validate
    from lfx.field_typing.constants import DEFAULT_IMPORT_STRING
    from lfx.interface.initialize import loading

    def augment(code: str) -> str:
        code = code.replace("from langflow import CustomComponent", "from langflow.custom import CustomComponent")
        code = code.replace(
            "from langflow.interface.custom.custom_component import CustomComponent",
            "from langflow.custom import CustomComponent",
        )
        return DEFAULT_IMPORT_STRING + "\n" + code

    def name_from_module(module, code: str) -> str:
        for node in module.body:
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and any(p in base.id for p in ["Component", "LC"]):
                        return node.name
        msg = f"No Component subclass found in the code string. Code snippet: {code[:100]}"
        raise TypeError(msg)

    def single_parse(code: str):
        if not hasattr(ast, "TypeIgnore"):
            ast.TypeIgnore = validate.create_type_ignore_class()
        try:
            module = ast.parse(augment(code))  # ONE parse instead of two
            class_name = name_from_module(module, code)
            exec_globals = validate.prepare_global_scope(module)
            future_imports = [n for n in module.body if isinstance(n, ast.ImportFrom) and n.module == "__future__"]
            class_code = validate.extract_class_code(module, class_name)
            compiled = validate.compile_class_code(class_code, future_imports)
            return validate.build_class_constructor(compiled, exec_globals, class_name)
        except SyntaxError as e:
            msg = f"Syntax error in code: {e!s}"
            raise ValueError(msg) from e

    loading.eval_custom_component_code = single_parse
    return single_parse


def install_both() -> None:
    """Cache AND single-parse together."""
    from lfx.interface.initialize import loading

    single = install_parse_dedup()
    loading.eval_custom_component_code = functools.lru_cache(maxsize=512)(single)


def patch_is_shipped() -> bool:
    from lfx.custom.eval import eval_custom_component_code as ev

    return hasattr(ev, "cache_info")


# --------------------------------------------------------------------------
# workloads
# --------------------------------------------------------------------------
def build_payload():
    """A 2-node ChatInput -> ChatOutput flow, dumped to the same JSON the API builds from."""
    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.graph import Graph

    ci = ChatInput(_id="ci")
    ci.set(input_value="hello world")
    co = ChatOutput(_id="co")
    co.set(input_value=ci.message_response)
    payload = Graph(start=ci, end=co, flow_id="00000000-0000-0000-0000-000000000001", flow_name="bench").dump()
    return payload.get("data", payload)


async def run_flow(data) -> object:
    from lfx.graph.graph.base import Graph

    g = Graph.from_payload(data, flow_id="00000000-0000-0000-0000-000000000001", flow_name="bench")
    async for _ in g.async_start():
        pass
    return g


async def sample_cpu_ms(data, inner: int) -> float:
    await run_flow(data)  # warm
    start = time.process_time()
    for _ in range(inner):
        await run_flow(data)
    return (time.process_time() - start) / inner * 1000


def bench_build_only(path: str, inner: int = 25) -> float:
    """CPU per Graph.from_payload for a real starter flow (build only, no execution)."""
    from lfx.graph.graph.base import Graph

    raw = json.load(open(path))
    data = raw.get("data", raw)
    Graph.from_payload(data, flow_id="warm", flow_name="b")
    start = time.process_time()
    for i in range(inner):
        Graph.from_payload(data, flow_id=f"f{i}", flow_name="b")
    return (time.process_time() - start) / inner * 1000


# --------------------------------------------------------------------------
# safety checks
# --------------------------------------------------------------------------
def class_snapshot(cls) -> dict:
    """Deep snapshot of every mutable attribute reachable on the class."""
    snap = {}
    for key in dir(cls):
        if key.startswith("__"):
            continue
        try:
            val = inspect.getattr_static(cls, key)
        except Exception:
            continue
        if isinstance(val, (list, dict, set)):
            try:
                snap[key] = copy.deepcopy(val)
            except Exception:
                snap[key] = repr(val)
    return snap


async def safety_checks(data) -> list[tuple[str, bool, str]]:
    """Returns [(check_name, passed, detail)]."""
    from lfx.graph.graph.base import Graph

    results = []

    # 1. class object is actually shared across builds
    g1 = Graph.from_payload(data, flow_id="a", flow_name="x")
    g2 = Graph.from_payload(data, flow_id="b", flow_name="x")
    t1 = {v.id: type(v.custom_component) for v in g1.vertices if getattr(v, "custom_component", None)}
    t2 = {v.id: type(v.custom_component) for v in g2.vertices if getattr(v, "custom_component", None)}
    shared = sum(1 for k in t1 if t2.get(k) is t1[k])
    results.append(("class object reused across builds", shared == len(t1), f"{shared}/{len(t1)}"))

    # 2. class state does not drift across many executions
    before = {k: class_snapshot(c) for k, c in t1.items()}
    for _ in range(20):
        await run_flow(data)
    after = {k: class_snapshot(c) for k, c in t1.items()}
    drift = [k for k in before if before[k] != after[k]]
    results.append(("no class-state drift over 20 runs", not drift, f"drifted: {drift or 'none'}"))

    # 3. distinct inputs produce distinct outputs (no cross-contamination)
    outs = []
    for token in ("ALPHA", "BETA", "GAMMA"):
        g = Graph.from_payload(data, flow_id="00000000-0000-0000-0000-000000000001", flow_name="x")
        for v in g.vertices:
            if v.id.startswith("ci"):
                v.update_raw_params({"input_value": token}, overwrite=True)
        async for _ in g.async_start():
            pass
        got = next((str(v.built_object) for v in g.vertices if v.id.startswith("co")), "")
        outs.append(token in got)
    results.append(("distinct inputs -> distinct outputs", all(outs), f"{sum(outs)}/3 correct"))

    # 4. every bundled component class survives instantiation without mutating itself
    import importlib
    import pkgutil

    import lfx.components as C
    from lfx.custom.custom_component.component import Component

    classes = {}
    for m in pkgutil.walk_packages(C.__path__, C.__name__ + "."):
        try:
            mod = importlib.import_module(m.name)
        except Exception:
            continue
        for obj in vars(mod).values():
            if inspect.isclass(obj) and issubclass(obj, Component) and obj is not Component:
                classes[f"{obj.__module__}.{obj.__name__}"] = obj
    violations, checked = [], 0
    for fq, cls in classes.items():
        snap = class_snapshot(cls)
        try:
            inst = cls()
            checked += 1
            try:
                inst.to_frontend_node()
            except Exception:
                pass
        except Exception:
            continue
        if class_snapshot(cls) != snap:
            violations.append(fq)
    results.append(
        (
            f"no class mutation across {checked} component classes",
            not violations,
            f"violations: {violations or 'none'}",
        )
    )
    return results


# --------------------------------------------------------------------------
def bar(value: float, peak: float, width: int = 42) -> str:
    filled = max(1, round(value / peak * width)) if peak else 0
    return "█" * filled + "·" * (width - filled)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flow", default="src/lfx/tests/fixtures/starter_flows/v1.9.0/basic_prompting.json")
    ap.add_argument("--repeats", type=int, default=REPEATS)
    ap.add_argument("--inner", type=int, default=INNER)
    args = ap.parse_args()

    print(f"python      : {sys.version.split()[0]}")
    print(f"patch shipped in checkout: {patch_is_shipped()}")
    print(f"samples     : {args.repeats} x {args.inner} runs, reporting median\n")

    data = build_payload()

    # ---- arm A: stock (no cache) ----
    uninstall_cache()
    a_e2e = statistics.median([await sample_cpu_ms(data, args.inner) for _ in range(args.repeats)])
    a_build = statistics.median([bench_build_only(args.flow) for _ in range(args.repeats)])

    # ---- arm B: cached ----
    install_cache()
    b_e2e = statistics.median([await sample_cpu_ms(data, args.inner) for _ in range(args.repeats)])
    b_build = statistics.median([bench_build_only(args.flow) for _ in range(args.repeats)])

    # ---- four-way build comparison on a real starter flow ----
    arms = [
        ("stock", uninstall_cache),
        ("parse-dedup only", install_parse_dedup),
        ("cache only (this patch)", install_cache),
        ("both", install_both),
    ]
    build = {}
    for label, setup in arms:
        setup()
        build[label] = statistics.median([bench_build_only(args.flow) for _ in range(args.repeats)])

    peak = max(max(build.values()), a_e2e)
    print("CPU per request (lower is better)\n")
    print("  2-node flow, build + execute")
    print(f"    stock                   {bar(a_e2e, peak)} {a_e2e:6.2f} ms")
    print(f"    cache only (this patch) {bar(b_e2e, peak)} {b_e2e:6.2f} ms   {a_e2e / b_e2e:.2f}x")
    print(f"\n  {os.path.basename(args.flow)}, build only")
    for label, _ in arms:
        v = build[label]
        print(f"    {label:<23} {bar(v, peak)} {v:6.2f} ms   {build['stock'] / v:.2f}x")
    print(f"\n  throughput ceiling per core: {1000 / a_e2e:.0f} -> {1000 / b_e2e:.0f} req/s")
    print(f"  parse-dedup alone           : saves {build['stock'] - build['parse-dedup only']:.2f} ms")
    print(f"  parse-dedup on top of cache : saves {build['cache only (this patch)'] - build['both']:.2f} ms")

    install_cache()
    print("\nSafety checks (with cache active)\n")
    ok = True
    for name, passed, detail in await safety_checks(data):
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:<48} {detail}")

    print(f"\nRESULT: {'all safety checks passed' if ok else 'SAFETY CHECK FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
