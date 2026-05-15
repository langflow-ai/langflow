"""Phase B orchestrator.

Control-plane responsibilities:
- start the Runtime API
- seed the variables the flow will need
- mint a per-run token with the right scopes
- build a scrubbed env for the worker subprocess (no DB creds, no provider keys)
- spawn the worker subprocess
- capture its outcome and verify the boundary held

The lfx process runs as the worker subprocess. The orchestrator never imports lfx.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

PROTOTYPE_ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = PROTOTYPE_ROOT / "flows" / "basic_prompting.json"
WORKER_SCRIPT = PROTOTYPE_ROOT / "scripts" / "worker.py"

API_HOST = "127.0.0.1"
API_PORT = 8767
API_URL = f"http://{API_HOST}:{API_PORT}"
SECRET = "phase-b-prototype-secret-must-be-at-least-32-bytes"


def _wait_for_port(host: str, port: int, *, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return
        except OSError:
            time.sleep(0.1)
    msg = f"port {host}:{port} did not come up within {timeout}s"
    raise RuntimeError(msg)


def _start_runtime_api() -> subprocess.Popen:
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "runtime_api.main:app",
            "--host",
            API_HOST,
            "--port",
            str(API_PORT),
            "--log-level",
            "warning",
        ],
        cwd=str(PROTOTYPE_ROOT),
        env={**os.environ, "RUNTIME_API_SECRET": SECRET},
    )
    _wait_for_port(API_HOST, API_PORT)
    return proc


def _seed_and_mint(client: httpx.Client, *, scopes: list[str]) -> tuple[str, str]:
    """Seed OPENAI_API_KEY and mint a run token with the given scopes.

    The caller controls scopes so we can also exercise the negative path
    (empty scopes -> worker should be denied at variable lookup time).
    """
    openai_key = os.environ.get("OPENAI_API_KEY", "MOCK-not-a-real-key")
    client.post(
        "/admin/seed-variable",
        json={"tenant_id": "t1", "name": "OPENAI_API_KEY", "value": openai_key},
    ).raise_for_status()

    r = client.post(
        "/admin/mint-token",
        json={
            "tenant_id": "t1",
            "user_id": "u1",
            "flow_id": "basic_prompting",
            "run_id": "run-1",
            "component_id": "lfx-worker",
            "scopes": scopes,
            "ttl_seconds": 300,
        },
    )
    r.raise_for_status()
    provider = "openai" if not openai_key.startswith("MOCK") else "mock"
    return r.json()["token"], provider


def _build_worker_env(token: str) -> dict[str, str]:
    """Scrub everything the worker shouldn't see. Keep PATH + Python pieces."""
    keep_prefixes = ("PATH", "PYTHONPATH", "PYTHON", "HOME", "USER", "LANG", "LC_", "TZ")
    keep_exact = {"VIRTUAL_ENV"}
    env: dict[str, str] = {}
    for k, v in os.environ.items():
        if k in keep_exact or any(k.startswith(p) for p in keep_prefixes):
            env[k] = v
    # Explicitly drop anything DB- or provider-related even if it matched
    # a prefix by accident (e.g. PG* env vars).
    for forbidden in (
        "LANGFLOW_DATABASE_URL",
        "DATABASE_URL",
        "POSTGRES_URL",
        "PGHOST",
        "PGUSER",
        "PGPASSWORD",
        "PGDATABASE",
        "SQLALCHEMY_DATABASE_URI",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
    ):
        env.pop(forbidden, None)
    env["MT_RUN_TOKEN"] = token
    env["MT_RUNTIME_API_URL"] = API_URL
    env["FLOW_PATH"] = str(FLOW_PATH)
    env["INPUT_TEXT"] = "Hi, who are you?"
    return env


def _run_worker(env: dict[str, str]) -> dict:
    result = subprocess.run(
        [sys.executable, str(WORKER_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(PROTOTYPE_ROOT),
    )
    last_line = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    try:
        outcome = json.loads(last_line)
    except json.JSONDecodeError:
        return {
            "status": "unparseable",
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-2000:],
        }
    return outcome


def main() -> int:
    deny_mode = "--deny" in sys.argv
    scopes: list[str] = [] if deny_mode else ["variables:read:OPENAI_API_KEY"]
    if deny_mode:
        print("==> --deny mode: minting token with NO scopes; expecting boundary refusal")

    print(f"==> Starting Runtime API on {API_URL}")
    api_proc = _start_runtime_api()
    try:
        with httpx.Client(base_url=API_URL, timeout=5.0) as admin:
            token, provider = _seed_and_mint(admin, scopes=scopes)
            print(f"==> Seeded OPENAI_API_KEY (provider={provider}) and minted run token (scopes={scopes})")

            env = _build_worker_env(token)
            # Defensive sanity check: confirm the worker env is scrubbed.
            leaked = [
                k
                for k in env
                if k
                in (
                    "LANGFLOW_DATABASE_URL",
                    "DATABASE_URL",
                    "OPENAI_API_KEY",
                    "PGHOST",
                    "PGUSER",
                    "PGPASSWORD",
                )
            ]
            if leaked:
                print(f"FAIL  scrub failed; worker would inherit: {leaked}")
                return 1
            print("OK    worker env scrubbed of DB/provider credentials")

            print(f"==> Spawning worker subprocess: {WORKER_SCRIPT.name}")
            outcome = _run_worker(env)
            print(f"==> Worker outcome: status={outcome.get('status')}")

            if deny_mode:
                # The boundary should hold: worker should report denied (or
                # propagate the PermissionError as a build error). Either way,
                # not 'ok'.
                ok_after_denial = outcome.get("status") == "ok"
                error_blob = json.dumps(outcome)[:500]
                if ok_after_denial:
                    print(f"FAIL  scope-less token still produced ok: {error_blob}")
                    return 1
                print(f"OK    boundary refused: {error_blob}")
                return 0

            if outcome.get("status") == "ok":
                print()
                print("Final output:")
                print(f"  {outcome.get('text') or '(no text returned)'}")
            elif outcome.get("status") == "denied":
                print(f"  denied: {outcome.get('error')}")
                return 1
            elif outcome.get("status") == "boot_failed":
                print(f"  boot_failed: {outcome}")
                return 1
            else:
                print(json.dumps(outcome, indent=2)[:1500])
                return 1

            # Verify the variable read went through the Runtime API.
            events = admin.get("/admin/events").json()
            reads = [
                e
                for e in events
                if e.get("kind") == "variable_read" and e.get("name") == "OPENAI_API_KEY" and e.get("tenant_id") == "t1"
            ]
            print()
            if reads:
                print(f"OK    variable lookup went through Runtime API ({len(reads)} read(s) logged)")
                return 0
            print("FAIL  no Runtime API event logged; the boundary was bypassed")
            return 1
    finally:
        api_proc.terminate()
        try:
            api_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            api_proc.kill()


if __name__ == "__main__":
    sys.exit(main())
