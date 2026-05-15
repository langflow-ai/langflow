"""Phase B worker subprocess.

What this proves:
- A real Langflow flow JSON runs through real lfx code in an isolated
  subprocess that holds NO database credentials and NO provider keys in
  its environment.
- The subprocess receives only a short-lived run token and the Runtime
  API URL. Every variable lookup goes through the capability shim.
- If LANGFLOW_DATABASE_URL or similar leaks into the env, the worker
  refuses to start, identically to the clean-room worker's boot check.

Inputs (env):
    RUN_TOKEN, RUNTIME_API_URL, FLOW_PATH, INPUT_TEXT
    MT_RUN_TOKEN, MT_RUNTIME_API_URL (set by the orchestrator before spawn)

Output (stdout): a single trailing JSON line with the outcome.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import traceback
from pathlib import Path
from urllib.parse import quote

import httpx

PROTOTYPE_ROOT = Path(__file__).resolve().parents[1]
if str(PROTOTYPE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE_ROOT))

# The lfx process IS the worker tier in this prototype. Treat its env as a
# sandbox surface: refuse to boot if anything that smells like DB or
# provider credentials leaked in.
FORBIDDEN_ENV = (
    "LANGFLOW_DATABASE_URL",
    "DATABASE_URL",
    "POSTGRES_URL",
    "PGHOST",
    "PGUSER",
    "PGPASSWORD",
    "PGDATABASE",
    "SQLALCHEMY_DATABASE_URI",
    # Provider keys must not be in the worker env: the design's whole
    # point is fetching them through capabilities.
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
)


def _emit(outcome: dict) -> None:
    sys.stdout.write(json.dumps(outcome) + "\n")
    sys.stdout.flush()


async def _attack_runtime_variable_read(name: str) -> dict:
    """Simulate hostile same-process code reusing the worker's run token.

    This deliberately does not print the secret value. A successful 200 proves
    code in the worker process can directly exercise the token's variable scope.
    """
    base_url = os.environ["MT_RUNTIME_API_URL"].rstrip("/")
    token = os.environ["MT_RUN_TOKEN"]
    url = f"{base_url}/runtime/variables/{quote(name, safe='')}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"})

    if response.status_code == 200:
        value = response.json().get("value", "")
        value_text = str(value)
        return {
            "status": "attack_succeeded",
            "attack": "direct_runtime_api_variable_read",
            "variable": name,
            "value_len": len(value_text),
            "value_sha256_12": hashlib.sha256(value_text.encode("utf-8")).hexdigest()[:12],
        }

    return {
        "status": "attack_blocked",
        "attack": "direct_runtime_api_variable_read",
        "variable": name,
        "http_status": response.status_code,
        "body": response.text[:300],
    }


async def _run() -> dict:
    # Register the capability-backed variable service. The decorator on
    # import time replaces lfx's default. Must happen BEFORE the graph
    # builds any vertex.
    import capability_variable_service  # noqa: F401
    from lfx.load import aload_flow_from_json
    from lfx.run._defaults import apply_run_defaults
    from lfx.schema.schema import InputValueRequest

    flow_path = os.environ["FLOW_PATH"]
    input_text = os.environ.get("INPUT_TEXT", "Hi, who are you?")

    graph = await aload_flow_from_json(flow_path, disable_logs=True)
    apply_run_defaults(graph, session_id=None, user_id=None)
    if stop_vertex_id := os.environ.get("MT_STOP_VERTEX_ID"):
        graph.prepare(stop_component_id=stop_vertex_id)
        results = []
        while True:
            r = await graph.astep(InputValueRequest(input_value=input_text))
            results.append(r)
            vertex = getattr(r, "vertex", None)
            if vertex is not None and vertex.id == stop_vertex_id:
                text = _text_from_results(results)
                return {"text": text, "stopped_at": stop_vertex_id}
            if vertex is None:
                return {"text": _text_from_results(results), "stopped_at": None}

    graph.prepare()

    results = []
    async for r in graph.async_start(InputValueRequest(input_value=input_text)):
        results.append(r)

    return {"text": _text_from_results(results)}


def _text_from_results(results: list) -> str | None:
    # Pull the assistant text out of the last vertex with a results dict.
    for r in reversed(results):
        vertex = getattr(r, "vertex", None)
        if vertex is None:
            continue
        vres = getattr(vertex, "results", None)
        if isinstance(vres, dict):
            for v in vres.values():
                text = _text_of(v)
                if text:
                    return text
        text = _text_of(vres)
        if text:
            return text
    return None


def _text_of(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value
    for attr in ("text", "message", "data"):
        sub = getattr(value, attr, None)
        if isinstance(sub, str) and sub.strip():
            return sub
        if isinstance(sub, dict):
            for k in ("text", "message"):
                if isinstance(sub.get(k), str) and sub[k].strip():
                    return sub[k]
    if isinstance(value, dict):
        for k in ("text", "message"):
            if isinstance(value.get(k), str) and value[k].strip():
                return value[k]
    return None


def main() -> int:
    leaked = [name for name in FORBIDDEN_ENV if name in os.environ]
    if leaked:
        _emit({"status": "boot_failed", "reason": "forbidden_env", "vars": leaked})
        return 2
    required = ("MT_RUN_TOKEN", "MT_RUNTIME_API_URL", "FLOW_PATH")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        _emit({"status": "boot_failed", "reason": "missing_env", "missing": missing})
        return 2
    try:
        if attack_variable_name := os.environ.get("MT_ATTACK_VARIABLE_NAME"):
            result = asyncio.run(_attack_runtime_variable_read(attack_variable_name))
            _emit(result)
            return 0
        result = asyncio.run(_run())
        _emit({"status": "ok", **result})
        return 0
    except PermissionError as exc:
        _emit({"status": "denied", "error": str(exc)})
        return 0
    except Exception as exc:  # noqa: BLE001
        _emit(
            {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc()[-2000:],
            }
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
