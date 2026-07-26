"""API key provisioning helpers."""

from __future__ import annotations

from typing import Any

from tests.locust.langflow_runtime.provision.api import ProvisionHttp
from tests.locust.langflow_runtime.provision.state import register_resource


def api_key_name(env_id: str) -> str:
    return f"perf-{env_id}-key"


def create_suite_api_key(http: ProvisionHttp, state: dict[str, Any]) -> dict[str, Any]:
    env_id = str(state["env_id"])
    name = api_key_name(env_id)
    created = http.create_api_key(name)
    api_key = created.get("api_key")
    api_key_id = created.get("id")
    if not api_key or not api_key_id:
        msg = f"create_api_key response missing fields: {created}"
        raise RuntimeError(msg)
    state["api_key"] = api_key
    state["api_key_id"] = str(api_key_id)
    state.setdefault("credentials", {})["api_key"] = api_key
    state["credentials"]["api_key_id"] = str(api_key_id)
    http.api_key = str(api_key)
    register_resource(
        state,
        kind="api_key",
        resource_id=str(api_key_id),
        name=name,
        env_id=env_id,
    )
    return created
