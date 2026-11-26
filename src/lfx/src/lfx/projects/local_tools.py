"""Reviewed definitions for a harness's local callable flows."""

from pydantic import Field

from lfx.projects.bindings import BoundFlowDependency, FlowSourceChangedError, flow_revision
from lfx.projects.dependencies import binding_dependencies


class LocalToolBinding(BoundFlowDependency):
    dependencies: list[BoundFlowDependency] = Field(default_factory=list)

    def definition(self) -> dict:
        return {
            **super().definition(),
            "dependencies": [item.definition() for item in sorted(self.dependencies, key=lambda item: item.flow_id)],
        }


def local_tool_definition(source: dict, definitions: list[dict]) -> LocalToolBinding:
    from lfx.projects.tools import validate_tool_flow

    validate_tool_flow(source)
    return LocalToolBinding(
        flow_id=str(source["id"]),
        name=source["name"],
        description=source.get("description") or "",
        revision=flow_revision(source["data"]),
        dependencies=binding_dependencies(str(source["id"]), definitions),
    )


def local_tool_bindings(value: object) -> dict[str, LocalToolBinding]:
    if not isinstance(value, dict):
        msg = "Local tool bindings must be keyed by their selected flow ID."
        raise TypeError(msg)
    result = {key: LocalToolBinding.model_validate(item) for key, item in value.items()}
    if any(key != item.flow_id for key, item in result.items()):
        msg = "A local tool binding points to a different flow. Review its selection."
        raise ValueError(msg)
    return result


def validate_local_tool_source(source: dict, binding: LocalToolBinding) -> None:
    from lfx.projects.tools import validate_tool_flow

    if (
        str(source.get("id")) != binding.flow_id
        or source.get("name") != binding.name
        or (source.get("description") or "") != binding.description
        or flow_revision(source.get("data") or {}) != binding.revision
    ):
        msg = "The local tool changed. Review its definition and save the harness before running."
        raise FlowSourceChangedError(msg)
    validate_tool_flow(source)
