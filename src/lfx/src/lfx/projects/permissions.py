"""Resolve reviewed PermissionGate flows using the shared isolated flow executor."""

from langchain_core.runnables import RunnableLambda
from pydantic import Field

from lfx.base.agents.permissions import Permission, PermissionSourceChangedError
from lfx.projects.bindings import FlowBinding, contract_outputs, flow_revision
from lfx.projects.invocation import ReviewedFlowRunner

PERMISSION_INPUT = "harness_permission_request"


class PermissionBinding(FlowBinding):
    timeout_seconds: float = Field(default=10, gt=0, le=300)


def parse_permission_binding(value: str) -> PermissionBinding | None:
    return PermissionBinding.model_validate_json(value) if value.strip() not in {"", "null", "{}"} else None


def permission_outputs(data: dict) -> list[dict]:
    sources = [node for node in data.get("nodes", []) if node.get("data", {}).get("type") == "PermissionRequest"]
    if len(sources) != 1:
        msg = "A permission flow needs one Permission Request connected to a Permission output."
        raise ValueError(msg)
    reachable = {sources[0]["id"]}
    for _ in data.get("nodes", []):
        reachable.update(edge["target"] for edge in data.get("edges", []) if edge.get("source") in reachable)
    return [choice for choice in contract_outputs(data, {"Permission"}) if choice["node_id"] in reachable]


def validate_permission_binding(data: dict, binding: FlowBinding) -> None:
    if not any(
        output["node_id"] == binding.node_id and output["output_name"] == binding.output_name
        for output in permission_outputs(data)
    ):
        msg = "Connect Permission Request to the selected Permission output before running."
        raise ValueError(msg)
    if flow_revision(data) != binding.revision:
        msg = "The permission flow changed. Review it and update its binding before running."
        raise PermissionSourceChangedError(msg)


class PermissionFlowRunner:
    def __init__(self, component, binding: PermissionBinding):
        self.component = component
        self.binding = binding
        self.runner = ReviewedFlowRunner(component, validate=validate_permission_binding, label="permission")

    async def __call__(self, payload: dict) -> Permission:
        async def invoke(request):
            parent = self.component.graph
            value = await self.runner(
                self.binding,
                {
                    PERMISSION_INPUT: {
                        **request,
                        "run_id": str(parent.run_id) if parent else None,
                        "session_id": getattr(parent, "session_id", None),
                    }
                },
            )
            if not isinstance(value, Permission):
                msg = "A permission flow must return Permission, not a display artifact."
                raise TypeError(msg)
            return value

        return await RunnableLambda(invoke, name="harness_permission_flow").ainvoke(
            payload, config={"tags": ["harness:permission"]}
        )
