"""Phase B orchestrator.

Control-plane responsibilities:
- start the Runtime API
- seed the variables the flow will need
- mint a per-run token with the right scopes
- build a scrubbed env for the worker subprocess (no DB creds, no provider keys)
- spawn the worker subprocess
- capture its outcome and verify the boundary held

The lfx execution process runs as the worker subprocess. The graph-aware
split-worker mode imports lfx only to inspect graph metadata for planning.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from per_vertex_plan import VertexCapabilityPlan, build_vertex_capability_plan

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


def _seed_variable(client: httpx.Client) -> str:
    """Seed OPENAI_API_KEY and return whether it looks real or mocked."""
    openai_key = os.environ.get("OPENAI_API_KEY", "MOCK-not-a-real-key")
    client.post(
        "/admin/seed-variable",
        json={"tenant_id": "t1", "name": "OPENAI_API_KEY", "value": openai_key},
    ).raise_for_status()
    return "openai" if not openai_key.startswith("MOCK") else "mock"


def _mint_token(client: httpx.Client, *, component_id: str, scopes: list[str]) -> str:
    r = client.post(
        "/admin/mint-token",
        json={
            "tenant_id": "t1",
            "user_id": "u1",
            "flow_id": "basic_prompting",
            "run_id": "run-1",
            "component_id": component_id,
            "scopes": scopes,
            "ttl_seconds": 300,
        },
    )
    r.raise_for_status()
    return r.json()["token"]


def _seed_and_mint(client: httpx.Client, *, scopes: list[str]) -> tuple[str, str]:
    """Seed OPENAI_API_KEY and mint a run token with the given scopes.

    The caller controls scopes so we can also exercise the negative path
    (empty scopes -> worker should be denied at variable lookup time).
    """
    provider = _seed_variable(client)
    token = _mint_token(client, component_id="lfx-worker", scopes=scopes)
    return token, provider


def _build_worker_env(
    token: str,
    *,
    attack_variable_name: str | None = None,
    stop_vertex_id: str | None = None,
) -> dict[str, str]:
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
    if attack_variable_name:
        env["MT_ATTACK_VARIABLE_NAME"] = attack_variable_name
    if stop_vertex_id:
        env["MT_STOP_VERTEX_ID"] = stop_vertex_id
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


def _format_plan(plan: VertexCapabilityPlan) -> str:
    scopes = ", ".join(plan.scopes) if plan.scopes else "none"
    return f"{plan.vertex_id} ({plan.display_name}, {plan.trust}, scopes={scopes})"


def _synthetic_attacker_plan() -> VertexCapabilityPlan:
    return VertexCapabilityPlan(
        vertex_id="synthetic-custom-component-probe",
        display_name="Synthetic Custom Component Probe",
        component_type="CustomComponent",
        trust="untrusted",
        scopes=(),
        reasons=("no custom component exists in Basic Prompting; probing the untrusted vertex boundary",),
        predecessors=(),
        upstream=(),
        successors=(),
    )


def main() -> int:
    deny_mode = "--deny" in sys.argv
    attack_mode = "--attack" in sys.argv
    split_worker_mode = "--split-workers" in sys.argv or "--per-vertex" in sys.argv
    scopes: list[str] = [] if deny_mode else ["variables:read:OPENAI_API_KEY"]
    attack_variable_name = "OPENAI_API_KEY" if attack_mode else None
    if deny_mode:
        print("==> --deny mode: minting token with NO scopes; expecting boundary refusal")
    if attack_mode:
        print("==> --attack mode: same-process code will call Runtime API directly with the worker token")
    if split_worker_mode:
        print("==> --split-workers mode: planning real graph vertices and minting per-vertex tokens")

    print(f"==> Starting Runtime API on {API_URL}")
    api_proc = _start_runtime_api()
    try:
        with httpx.Client(base_url=API_URL, timeout=5.0) as admin:
            if split_worker_mode:
                plans = asyncio.run(build_vertex_capability_plan(FLOW_PATH))
                untrusted_plans = [plan for plan in plans if plan.is_untrusted] or [_synthetic_attacker_plan()]
                scoped_plans = [plan for plan in plans if plan.scopes]
                untrusted_vertex_ids = {plan.vertex_id for plan in plans if plan.is_untrusted}
                unsafe_scoped_plans = [
                    plan for plan in scoped_plans if untrusted_vertex_ids.intersection(plan.upstream)
                ]

                print(f"==> Planned {len(plans)} real flow vertices")
                for plan in plans:
                    print(f"PLAN  {_format_plan(plan)}")
                if not scoped_plans:
                    print("FAIL  no scoped vertices found; expected Basic Prompting to need OPENAI_API_KEY")
                    return 1
                if unsafe_scoped_plans:
                    for plan in unsafe_scoped_plans:
                        print(f"BLOCK {_format_plan(plan)} has untrusted upstream: {sorted(plan.upstream)}")
                    print("FAIL  prototype cannot safely run scoped vertices with untrusted upstream in-process")
                    return 1

                provider = _seed_variable(admin)
                print(f"==> Seeded OPENAI_API_KEY (provider={provider})")

                for plan in untrusted_plans:
                    token = _mint_token(admin, component_id=plan.vertex_id, scopes=[])
                    print(f"==> Minted untrusted vertex token for {plan.vertex_id} (scopes=[])")
                    env = _build_worker_env(token, attack_variable_name="OPENAI_API_KEY")
                    outcome = _run_worker(env)
                    print(f"==> Untrusted vertex probe outcome: {plan.vertex_id} status={outcome.get('status')}")

                    if outcome.get("status") != "attack_blocked":
                        print(json.dumps(outcome, indent=2)[:1500])
                        print(f"FAIL  untrusted vertex {plan.vertex_id} should not read OPENAI_API_KEY")
                        return 1

                for plan in scoped_plans:
                    token = _mint_token(admin, component_id=plan.vertex_id, scopes=list(plan.scopes))
                    print(f"==> Minted scoped vertex token for {plan.vertex_id} (scopes={list(plan.scopes)})")
                    env = _build_worker_env(token, stop_vertex_id=plan.vertex_id)
                    outcome = _run_worker(env)
                    print(f"==> Scoped vertex outcome: {plan.vertex_id} status={outcome.get('status')}")

                    if outcome.get("status") != "ok" or outcome.get("stopped_at") != plan.vertex_id:
                        print(json.dumps(outcome, indent=2)[:1500])
                        print(f"FAIL  scoped vertex {plan.vertex_id} should complete with its own token")
                        return 1

                events = admin.get("/admin/events").json()
                custom_denials = [
                    e
                    for e in events
                    if e.get("kind") == "variable_denied"
                    and e.get("name") == "OPENAI_API_KEY"
                    and e.get("component_id") in {plan.vertex_id for plan in untrusted_plans}
                ]
                custom_reads = [
                    e
                    for e in events
                    if e.get("kind") == "variable_read"
                    and e.get("name") == "OPENAI_API_KEY"
                    and e.get("component_id") in {plan.vertex_id for plan in untrusted_plans}
                ]
                model_reads = [
                    e
                    for e in events
                    if e.get("kind") == "variable_read"
                    and e.get("name") == "OPENAI_API_KEY"
                    and e.get("component_id") in {plan.vertex_id for plan in scoped_plans}
                ]

                if custom_reads:
                    print("FAIL  untrusted vertex read OPENAI_API_KEY despite empty scopes")
                    return 1
                if len(custom_denials) < len(untrusted_plans):
                    print("FAIL  untrusted vertex was blocked without a Runtime API denial event")
                    return 1
                print(f"OK    untrusted vertex token(s) denied ({len(custom_denials)} denial(s) logged)")

                if len(model_reads) < len(scoped_plans):
                    print("FAIL  scoped vertex completed without a Runtime API variable read")
                    return 1
                print(f"OK    scoped vertex token(s) read through Runtime API ({len(model_reads)} read(s))")
                print("OK    graph-aware per-vertex token boundary validates the prototype direction")
                return 0

            token, provider = _seed_and_mint(admin, scopes=scopes)
            print(f"==> Seeded OPENAI_API_KEY (provider={provider}) and minted run token (scopes={scopes})")

            env = _build_worker_env(token, attack_variable_name=attack_variable_name)
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

            if attack_mode:
                events = admin.get("/admin/events").json()
                attack_reads = [
                    e
                    for e in events
                    if e.get("kind") == "variable_read"
                    and e.get("name") == "OPENAI_API_KEY"
                    and e.get("component_id") == "lfx-worker"
                ]
                attack_denials = [
                    e
                    for e in events
                    if e.get("kind") == "variable_denied"
                    and e.get("name") == "OPENAI_API_KEY"
                    and e.get("component_id") == "lfx-worker"
                ]

                if outcome.get("status") == "attack_succeeded":
                    print(
                        "FINDING same-process attacker reused the run token "
                        "to read OPENAI_API_KEY "
                        f"(len={outcome.get('value_len')}, sha256_12={outcome.get('value_sha256_12')})"
                    )
                    if attack_reads:
                        print(f"OK    Runtime API logged the attacker variable read ({len(attack_reads)} read(s))")
                    if deny_mode:
                        print("FAIL  scope-less attacker should not have read the variable")
                        return 1
                    print("NOTE  process-level isolation is not enough for hostile custom components")
                    return 0

                if outcome.get("status") == "attack_blocked":
                    print(
                        "OK    same-process attacker was blocked "
                        f"(http_status={outcome.get('http_status')})"
                    )
                    if attack_denials:
                        print(f"OK    Runtime API logged the attacker denial ({len(attack_denials)} denial(s))")
                        return 0
                    print("FAIL  attack was blocked, but no Runtime API denial was logged")
                    return 1

                print(json.dumps(outcome, indent=2)[:1500])
                return 1

            if deny_mode:
                # The boundary should hold: worker should report denied (or
                # propagate the PermissionError as a build error). Either way,
                # not 'ok'.
                ok_after_denial = outcome.get("status") == "ok"
                error_blob = json.dumps(outcome)[:500]
                if ok_after_denial:
                    print(f"FAIL  scope-less token still produced ok: {error_blob}")
                    return 1
                events = admin.get("/admin/events").json()
                denials = [
                    e
                    for e in events
                    if e.get("kind") == "variable_denied"
                    and e.get("name") == "OPENAI_API_KEY"
                    and e.get("tenant_id") == "t1"
                ]
                if not denials:
                    print(f"FAIL  boundary refused without a Runtime API denial event: {error_blob}")
                    return 1
                print(f"OK    boundary refused: {error_blob}")
                print(f"OK    Runtime API logged the denial ({len(denials)} denial(s))")
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
