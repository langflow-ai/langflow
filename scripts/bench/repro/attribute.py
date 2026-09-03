"""Attribute the query/CPU reduction to individual source changes.

Answers "which changes actually did the work" by measurement rather than by
reading diffs. Holds the branch, reverts ONE file to its base version, and
measures what is lost. A file whose reversion costs many queries per request is
carrying the win; one that costs nothing is not.

Queries per request is the primary signal: it is near-deterministic on this rig
(spread under 0.1 across repetitions), so single measurements are meaningful,
where p50 would need repetitions to say anything.

Contributions are NOT assumed additive -- interactions between changes are
plausible -- so the ranking produced here must be confirmed by building a branch
with only the top changes and measuring it directly.

  docker compose -f scripts/bench/repro/compose.yml up -d
  uv run python scripts/bench/repro/attribute.py --base <rev> --branch <rev>
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import os
import signal

from ab import (
    PORT,
    ROOT,
    changed_files,
    cpu_seconds,
    ensure_flow,
    materialise,
    preflight,
    restore,
    sh,
    start_server,
)


def measure(tag: str, out: Path, pool: str, conc: int, requests: int) -> dict | None:
    proc = start_server(tag, out, pool)
    try:
        flow_id = ensure_flow()
        c0 = cpu_seconds(proc.pid)
        r = sh(
            str(ROOT / ".venv/bin/python"),
            "-m",
            "db_profile.drive",
            "--workload",
            "run_flow",
            "--concurrency",
            str(conc),
            "--requests",
            str(requests),
            cwd=ROOT,
            env={
                **os.environ,
                "PYTHONPATH": "scripts/bench",
                "DB_PROFILE_BASE": f"http://127.0.0.1:{PORT}",
                "DB_PROFILE_FLOW_ID": flow_id,
            },
            check=False,
        )
        c1 = cpu_seconds(proc.pid)
        try:
            d = json.loads(r.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return None
        counts = sh(
            str(ROOT / ".venv/bin/python"),
            "scripts/bench/db_profile/per_request_counts.py",
            str(out / f"{tag}."),
            cwd=ROOT,
            check=False,
        ).stdout
        instr = json.loads(counts) if counts.strip().startswith("{") else {}
        return {
            "q": instr.get("queries_per_req"),
            "ck": instr.get("checkouts_per_req"),
            "cpu_ms": 1000.0 * (c1 - c0) / requests,
            "p50": d.get("p50_ms"),
            "rps": requests / d["wall_s"],
            "errors": d.get("errors"),
        }
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            proc.kill()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--rtt", type=int, default=15)
    ap.add_argument("--conc", type=int, default=10)
    ap.add_argument("--requests", type=int, default=150)
    ap.add_argument(
        "--pool",
        default='{"pool_size":10,"max_overflow":40,"pool_timeout":30,'
        '"pool_pre_ping":true,"pool_recycle":1800,"echo":false}',
    )
    ap.add_argument("--out", default="/tmp/repro_attr")  # noqa: S108
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    preflight(args.rtt)
    files = changed_files(args.base, args.branch)
    print(f"{len(files)} changed source files\n")

    rows = {}
    try:
        materialise(args.base, files)
        base = measure("attr_base", out, args.pool, args.conc, args.requests)
        print(f"{'BASE (all reverted)':<58} q/req={base['q']:.2f} cpu={base['cpu_ms']:.1f}")

        materialise(args.branch, files)
        full = measure("attr_branch", out, args.pool, args.conc, args.requests)
        print(f"{'BRANCH (all applied)':<58} q/req={full['q']:.2f} cpu={full['cpu_ms']:.1f}")
        print(f"\ntotal effect: {base['q'] - full['q']:.2f} queries/request removed\n")
        print(f"{'file reverted to base':<58}{'q/req':>8}{'queries lost':>14}")
        print("-" * 80)

        for f in files:
            materialise(args.branch, files)  # full branch
            sh("git", "-C", str(ROOT), "checkout", args.base, "--", f)  # then revert one file
            for pyc in ROOT.rglob("__pycache__"):
                shutil.rmtree(pyc, ignore_errors=True)
            tag = "attr_" + f.replace("/", "_").replace(".py", "").replace(".json", "")
            try:
                m = measure(tag, out, args.pool, args.conc, args.requests)
            except SystemExit as exc:
                # Reverting one file alone can break startup when another
                # changed file depends on it -- that is a real property of the
                # change set, not a harness failure. Record and continue.
                print(f"{f:<58}{'COUPLED':>8}   (cannot revert alone: {str(exc)[:60]})")
                rows[f] = {"q": None, "lost": None, "coupled": True}
                continue
            if m is None or m["q"] is None:
                print(f"{f:<58}{'FAILED':>8}")
                continue
            # A cell whose requests ERRORED issues few queries and looks like a
            # huge improvement. Reverting validate.py did exactly this: 40/40
            # HTTP 500 (branch eval.py calls a function only branch validate.py
            # defines) and it scored -9.40 q/req until the errors were checked.
            if m.get("errors"):
                print(
                    f"{f:<58}{'ERRORED':>8}   ({m['errors']} failed requests -- "
                    f"coupled to another change; not a contributor)"
                )
                rows[f] = {"q": None, "lost": None, "coupled": True, "errors": m["errors"]}
                continue
            lost = m["q"] - full["q"]
            rows[f] = {"q": m["q"], "lost": lost, "cpu_ms": m["cpu_ms"], "errors": m["errors"]}
            print(f"{f:<58}{m['q']:>8.2f}{lost:>14.2f}", flush=True)
    finally:
        restore()
        print("\nworking tree restored to HEAD")

    if rows:
        print("\n=== ranked by CPU ms per request lost when reverted ===")
        cpu_ranked = {k: v for k, v in rows.items() if v.get("cpu_ms") is not None}
        cpu_total = base["cpu_ms"] - full["cpu_ms"] if base and full else 0
        for f, v in sorted(cpu_ranked.items(), key=lambda kv: -(kv[1]["cpu_ms"] - full["cpu_ms"]))[:8]:
            lost = v["cpu_ms"] - full["cpu_ms"]
            share = 100 * lost / cpu_total if cpu_total else 0
            print(f"  {lost:>6.1f} ms/req ({share:>5.1f}% of the total)  {f}")
        print("  NOTE: CPU is noisier than query counts; treat gaps under ~2 ms as unresolved at n=1.")

        print("\n=== ranked by queries per request lost when reverted ===")
        ranked = {k: v for k, v in rows.items() if v.get("lost") is not None}
        for f, v in sorted(ranked.items(), key=lambda kv: -kv[1]["lost"])[:8]:
            share = 100 * v["lost"] / (base["q"] - full["q"]) if base and full else 0
            print(f"  {v['lost']:>6.2f} q/req ({share:>5.1f}% of the total)  {f}")
        (out / "attribution.json").write_text(json.dumps({"base": base, "branch": full, "per_file": rows}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
