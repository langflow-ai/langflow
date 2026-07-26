"""Project provisioning helpers."""

from __future__ import annotations

from typing import Any

from tests.locust.langflow_runtime.provision.api import ProvisionHttp
from tests.locust.langflow_runtime.provision.state import register_resource


def project_name(env_id: str, fixture_id: str) -> str:
    return f"perf-{env_id}-{fixture_id}"


def create_isolated_project(http: ProvisionHttp, state: dict[str, Any], *, fixture_id: str) -> dict[str, Any]:
    env_id = str(state["env_id"])
    name = project_name(env_id, fixture_id)
    created = http.create_project(name, description=f"perf suite project for {fixture_id} ({env_id})")
    project_id = created.get("id")
    if not project_id:
        msg = f"create_project response missing id: {created}"
        raise RuntimeError(msg)
    register_resource(
        state,
        kind="project",
        resource_id=str(project_id),
        name=name,
        env_id=env_id,
        extra={"fixture_id": fixture_id},
    )
    # First / primary project id for consumers that expect a single project_id.
    if not state.get("project_id"):
        state["project_id"] = str(project_id)
        state["project_name"] = name
    return created
