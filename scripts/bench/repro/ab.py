"""Reproducible base-vs-branch A/B for the DB-connection work. No bespoke rig.

WHAT THIS MEASURES, AND WHY THOSE METRICS

  queries per request   -- the causal quantity the branch changes.
  CPU ms per request    -- what sets the throughput ceiling: ceiling_rps =
                           1000 / cpu_ms_per_request.
  p50 / throughput      -- reported, but on a shared developer machine these are
                           the NOISIEST numbers here. Trust the two above.

The original measurements pinned a worker to one vCPU with ``taskset`` to make
the saturation cliff visible. That is Linux-only and is deliberately NOT
required here: CPU-per-request is measured directly from the server process, and
the ceiling follows from it arithmetically. Pinning demonstrates the cliff; it is
not needed to measure the effect.

USAGE

  docker compose -f scripts/bench/repro/compose.yml up -d
  uv run python scripts/bench/repro/ab.py --base <rev> --branch <rev> --reps 3
  docker compose -f scripts/bench/repro/compose.yml down -v

Arms are materialised by checking the two revisions' versions of the changed
files into THIS working tree and restoring afterwards, so both arms run against
one environment. The tree must be clean; the run refuses otherwise, because a
half-applied local edit would silently become part of an arm.

Everything external is verified before any number is produced -- notably the
injected latency is read BACK from toxiproxy, since its configuration is lost
whenever the container restarts and a silent 0ms run looks entirely normal.
"""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
import os
import shutil
import signal
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOXI_API = os.environ.get("REPRO_TOXIPROXY_API", "http://127.0.0.1:58474")
PG_DIRECT = os.environ.get("REPRO_PG_DIRECT", "127.0.0.1:55432")
PG_PROXIED = os.environ.get("REPRO_PG_PROXIED", "127.0.0.1:55433")
BENCH_FLOW_NAME = "repro_bench_flow"
DSN = f"postgresql://langflow:langflow@{PG_PROXIED}/langflow"
PORT = int(os.environ.get("REPRO_PORT", "7899"))
SUPERUSER = "admin"
SUPERUSER_PW = "admin12345"
HTTP_OK = 200
ALPHA = 0.05  # conventional significance threshold, used only for advice


def sh(*argv: str, check: bool = True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, check=check, **kw)  # noqa: S603


def api(method: str, path: str, payload: dict | None = None) -> dict | list | None:
    data = json.dumps(payload).encode() if payload is not None else None
    url = f"{TOXI_API}{path}"
    req = urllib.request.Request(  # noqa: S310 - fixed http scheme, host is a module constant
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
            body = r.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        if e.code in (404, 409):
            return None
        raise


def set_latency(ms: int) -> int:
    """Create the proxy and toxic, then READ IT BACK. Returns the verified value."""
    api("DELETE", "/proxies/pg")
    api("POST", "/proxies", {"name": "pg", "listen": "0.0.0.0:5433", "upstream": "postgres:5432", "enabled": True})
    if ms > 0:
        api(
            "POST",
            "/proxies/pg/toxics",
            {"name": "lat", "type": "latency", "stream": "downstream", "attributes": {"latency": ms, "jitter": 0}},
        )
    proxies = api("GET", "/proxies") or {}
    toxics = proxies.get("pg", {}).get("toxics", [])
    got = toxics[0]["attributes"]["latency"] if toxics else 0
    if got != ms:
        msg = f"latency read back as {got}ms, expected {ms}ms -- refusing to report numbers"
        raise SystemExit(msg)
    return got


def preflight(rtt: int) -> None:
    if shutil.which("docker") is None:
        msg = "docker not found"
        raise SystemExit(msg)
    dirty = sh("git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no").stdout.strip()
    if dirty:
        msg = f"working tree is dirty; commit or stash first:\n{dirty}"
        raise SystemExit(msg)
    try:
        api("GET", "/proxies")
    except Exception as exc:
        msg = (
            f"toxiproxy unreachable at {TOXI_API}: {exc}\n"
            "start it: docker compose -f scripts/bench/repro/compose.yml up -d"
        )
        raise SystemExit(msg) from exc
    got = set_latency(rtt)
    print(f"preflight OK: toxiproxy latency verified at {got}ms, tree clean")


def changed_files(base: str, branch: str) -> list[str]:
    out = sh("git", "-C", str(ROOT), "diff", "--name-only", f"{base}..{branch}", "--", "src/").stdout
    return [f for f in out.splitlines() if f.strip() and "/tests/" not in f and "/test/" not in f]


def materialise(rev: str, files: list[str]) -> None:
    sh("git", "-C", str(ROOT), "checkout", rev, "--", *files)
    diff = sh("git", "-C", str(ROOT), "diff", "--quiet", rev, "--", *files, check=False)
    if diff.returncode != 0:
        msg = f"tree does not match {rev} after checkout"
        raise SystemExit(msg)
    for pyc in ROOT.rglob("__pycache__"):
        shutil.rmtree(pyc, ignore_errors=True)


def restore() -> None:
    sh("git", "-C", str(ROOT), "checkout", "HEAD", "--", "src/")


def start_server(tag: str, out_dir: Path, pool: str) -> subprocess.Popen:
    env = {
        **os.environ,
        "PYTHONPATH": "scripts/bench",
        "DB_PROFILE_OUT": str(out_dir / f"{tag}.jsonl"),
        "LANGFLOW_DATABASE_URL": DSN,
        "LANGFLOW_DB_CONNECTION_SETTINGS": pool,
        "LANGFLOW_AUTO_LOGIN": "true",
        "LANGFLOW_SKIP_AUTH_AUTO_LOGIN": "true",
        "LANGFLOW_LOG_LEVEL": "critical",
        "LANGFLOW_PROMETHEUS_ENABLED": "false",
        "LANGFLOW_OPEN_BROWSER": "false",
        "LANGFLOW_RATE_LIMIT_PER_MINUTE": "1000000",
        "LANGFLOW_SUPERUSER": SUPERUSER,
        "LANGFLOW_SUPERUSER_PASSWORD": SUPERUSER_PW,
    }
    log = (out_dir / f"{tag}.server.log").open("w")
    proc = subprocess.Popen(  # noqa: S603
        [
            str(ROOT / ".venv/bin/uvicorn"),
            "db_profile.serve:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--workers",
            "1",
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    for _ in range(240):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2) as r:
                if r.status == HTTP_OK:
                    return proc
        except Exception:  # noqa: BLE001, S110
            pass
        if proc.poll() is not None:
            msg = f"server exited during startup; see {out_dir / f'{tag}.server.log'}"
            raise SystemExit(msg)
        time.sleep(1)
    proc.send_signal(signal.SIGTERM)
    msg = "server did not become healthy in 240s"
    raise SystemExit(msg)


def _read_json(resp) -> object:
    """Read a response body, gunzipping when the server compressed it.

    ``compress_response`` gzips the flows list unconditionally -- asking for
    ``Accept-Encoding: identity`` does not stop it -- and urllib does not
    decompress on its own.
    """
    raw = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def ensure_flow() -> str:
    """Create the benchmark flow if the (fresh) database has none.

    A brand-new Postgres has no flows, so the driver's run_flow workload would
    have nothing to call. The graph is deliberately trivial and identical across
    arms -- what is being compared is the code path, not the flow.
    """
    token_req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/api/v1/login",
        data=urllib.parse.urlencode({"username": SUPERUSER, "password": SUPERUSER_PW}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(token_req, timeout=30) as r:  # noqa: S310
        token = _read_json(r)["access_token"]
    hdr = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        # The flows list is gzipped by compress_response and urllib will not
        # decompress it; ask the server not to compress instead.
        "Accept-Encoding": "identity",
    }

    list_req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/v1/flows/", headers=hdr)
    with urllib.request.urlopen(list_req, timeout=60) as r:  # noqa: S310
        existing = _read_json(r)
    for f in existing:
        if f.get("name") == BENCH_FLOW_NAME:
            return f["id"]

    payload = json.dumps(
        {
            "name": BENCH_FLOW_NAME,
            "description": "reproducible A/B benchmark flow",
            "data": json.loads((Path(__file__).parent / "bench_flow.json").read_text()),
        }
    ).encode()
    create = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/v1/flows/", data=payload, headers=hdr, method="POST")
    with urllib.request.urlopen(create, timeout=60) as r:  # noqa: S310
        return _read_json(r)["id"]


def cpu_seconds(pid: int) -> float:
    import psutil

    p = psutil.Process(pid)
    t = p.cpu_times()
    total = t.user + t.system
    for c in p.children(recursive=True):
        try:
            ct = c.cpu_times()
            total += ct.user + ct.system
        except Exception:  # noqa: BLE001, S112
            continue
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="git revision for the base arm")
    ap.add_argument("--branch", required=True, help="git revision for the branch arm")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--rtt", type=int, default=15, help="injected one-way DB latency, ms")
    ap.add_argument("--conc", type=int, default=10)
    ap.add_argument("--requests", type=int, default=200)
    ap.add_argument(
        "--pool",
        default='{"pool_size":10,"max_overflow":40,"pool_timeout":30,'
        '"pool_pre_ping":true,"pool_recycle":1800,"echo":false}',
    )
    ap.add_argument("--out", default="/tmp/repro_ab")  # noqa: S108
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    preflight(args.rtt)

    files = changed_files(args.base, args.branch)
    if not files:
        msg = f"no source differences between {args.base} and {args.branch}"
        raise SystemExit(msg)
    print(f"{len(files)} changed source files define the two arms")
    print(f"pool pinned IDENTICALLY in both arms: {args.pool}\n")

    # The driver and the per-request counter run as subprocesses with their own
    # PYTHONPATH; check they exist rather than importing them into this process.
    for rel in ("scripts/bench/db_profile/drive.py", "scripts/bench/db_profile/per_request_counts.py"):
        if not (ROOT / rel).exists():
            msg = f"missing {rel} -- the db_profile harness must be present"
            raise SystemExit(msg)

    results: dict[str, list[dict]] = {"base": [], "branch": []}
    try:
        for rep in range(1, args.reps + 1):
            for arm, rev in (("base", args.base), ("branch", args.branch)):
                materialise(rev, files)
                tag = f"{arm}_r{rep}"
                proc = start_server(tag, out, args.pool)
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
                        str(args.conc),
                        "--requests",
                        str(args.requests),
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
                        print(f"[{tag}] driver produced no result:\n{r.stdout[-400:]}{r.stderr[-400:]}")
                        continue
                    counts = sh(
                        str(ROOT / ".venv/bin/python"),
                        "scripts/bench/db_profile/per_request_counts.py",
                        str(out / f"{tag}."),
                        cwd=ROOT,
                        check=False,
                    ).stdout
                    instr = json.loads(counts) if counts.strip().startswith("{") else {}
                    row = {
                        "arm": arm,
                        "rep": rep,
                        "p50": d.get("p50_ms"),
                        "wall": d.get("wall_s"),
                        "errors": d.get("errors"),
                        "rps": args.requests / d["wall_s"],
                        "cpu_ms": 1000.0 * (c1 - c0) / args.requests,
                        "queries_per_req": instr.get("queries_per_req"),
                        "checkouts_per_req": instr.get("checkouts_per_req"),
                    }
                    results[arm].append(row)
                    (out / f"{tag}.json").write_text(json.dumps(row, indent=2))
                    print(
                        f"[{tag}] q/req={row['queries_per_req']} cpu_ms={row['cpu_ms']:.1f} "
                        f"p50={row['p50']} rps={row['rps']:.2f} err={row['errors']}",
                        flush=True,
                    )
                finally:
                    proc.send_signal(signal.SIGTERM)
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        proc.kill()
    finally:
        restore()
        print("\nworking tree restored to HEAD")

    return report(results, args)


def report(results: dict[str, list[dict]], args) -> int:
    b, r = results["base"], results["branch"]
    if not b or not r:
        print("insufficient data")
        return 2
    print(
        f"\n=== base {args.base}  vs  branch {args.branch}   n={len(b)}/{len(r)}, "
        f"rtt={args.rtt}ms, conc={args.conc} ==="
    )
    print(f"{'metric':>20}{'base':>12}{'branch':>12}{'delta':>9}{'p':>8}")
    verdict = {}
    for key, label, lower_better in (
        ("queries_per_req", "queries/request", True),
        ("cpu_ms", "CPU ms/request", True),
        ("p50", "p50 ms", True),
        ("rps", "throughput req/s", False),
    ):
        bv = [x[key] for x in b if x.get(key) is not None]
        rv = [x[key] for x in r if x.get(key) is not None]
        if not bv or not rv:
            continue
        bm, rm = statistics.median(bv), statistics.median(rv)
        delta = 100 * (rm - bm) / bm
        p = perm_p(bv, rv, lower_better=lower_better)
        verdict[key] = (delta, p)
        print(f"{label:>20}{bm:>12.2f}{rm:>12.2f}{delta:>8.1f}%{p:>8.3f}")

    print("\nCPU-derived throughput ceiling (ceiling_rps = 1000 / CPU ms per request):")
    for name, rows in (("base", b), ("branch", r)):
        cm = statistics.median(x["cpu_ms"] for x in rows)
        print(f"  {name:>7}: {cm:6.1f} ms -> {1000 / cm:5.1f} req/s per core")

    # An exact permutation test on n vs n has a smallest attainable p of
    # 1/C(2n, n): 0.500 at n=1, 0.100 at n=3, 0.008 at n=5. Reporting p=0.100
    # without that context reads as "not significant" when it is in fact the
    # floor, which is a reporting bug this harness has already caused once.
    import math

    floor = 1.0 / math.comb(2 * len(b), len(b))
    print(
        f"\nSmallest attainable p at n={len(b)} is {floor:.3f} "
        f"(exact permutation, {math.comb(2 * len(b), len(b))} arrangements)."
    )
    if floor > ALPHA:
        print(f"  Use --reps 5 or more for p below {ALPHA}; at n={len(b)} the test cannot get there.")

    q = verdict.get("queries_per_req", (0, 1))
    c = verdict.get("cpu_ms", (0, 1))
    print("\nVERDICT")
    print(f"  queries/request {q[0]:+.1f}% (p={q[1]:.3f})   CPU/request {c[0]:+.1f}% (p={c[1]:.3f})")
    if q[0] < 0 and c[0] < 0:
        print("  -> the branch issues fewer queries AND uses less CPU per request.")
        print("     p50/throughput on a shared machine are noisy; the two metrics above are the claim.")
    else:
        print("  -> NOT reproduced on this machine. Do not report a speedup.")
    return 0


def perm_p(a: list[float], bb: list[float], *, lower_better: bool) -> float:
    """Exact one-sided permutation test on the difference of medians."""
    obs = statistics.median(a) - statistics.median(bb)
    if not lower_better:
        obs = -obs
    pool = a + bb
    n = len(a)
    cnt = tot = 0
    for idx in itertools.combinations(range(len(pool)), n):
        g1 = [pool[i] for i in idx]
        g2 = [pool[i] for i in range(len(pool)) if i not in idx]
        d = statistics.median(g1) - statistics.median(g2)
        if not lower_better:
            d = -d
        tot += 1
        if d >= obs:
            cnt += 1
    return cnt / tot


if __name__ == "__main__":
    sys.exit(main())
