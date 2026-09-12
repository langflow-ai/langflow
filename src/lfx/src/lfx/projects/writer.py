"""Writing a project's form through to its flows.

``project_config`` records what the user picked on the project's form. It is not what runs. The
value that runs is an input on a component in a flow file, because a flow file is the only
artifact both langflow and lfx load: langflow keeps it in a row, lfx reads it off disk, and
neither consults a folder to decide what a graph does.

So a field that declares a ``writes_to`` target is copied into every matching component in the
project's flows when the form is saved. A field with no target is recorded and nothing more.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.projects.schema import ProjectType


@dataclass(frozen=True)
class ConfigWrite:
    """The result of writing a config into one flow."""

    #: The flow's data, with the values applied. A copy; the input is left alone.
    data: dict
    #: How many component inputs were given a new value. Zero means the flow already agreed
    #: with the form, or holds no component the form targets.
    inputs_written: int

    @property
    def changed(self) -> bool:
        return self.inputs_written > 0


def _template_of(node: dict) -> dict[str, Any] | None:
    """The template of a flow node, or ``None`` when the node is not shaped like one."""
    data = node.get("data")
    if not isinstance(data, dict):
        return None
    inner = data.get("node")
    if not isinstance(inner, dict):
        return None
    template = inner.get("template")
    return template if isinstance(template, dict) else None


def apply_project_config(flow_data: dict | None, project_type: ProjectType, config: dict | None) -> ConfigWrite:
    """Copy ``config`` into the components of one flow, following the type's write-through targets.

    Only fields the type gives a ``writes_to`` are written, only into components whose type
    matches, and only into inputs that component already has. Nothing is invented: a target the
    flow has no component for, or a component without that input, is simply not written.
    """
    if not isinstance(flow_data, dict):
        return ConfigWrite(data=flow_data if isinstance(flow_data, dict) else {}, inputs_written=0)

    nodes = flow_data.get("nodes")
    if not isinstance(nodes, list):
        return ConfigWrite(data=flow_data, inputs_written=0)

    targets = [(field, field.writes_to) for field in project_type.fields if field.writes_to is not None]
    if not targets or not config:
        return ConfigWrite(data=flow_data, inputs_written=0)

    updated = deepcopy(flow_data)
    written = 0

    for node in updated.get("nodes", []):
        if not isinstance(node, dict):
            continue
        template = _template_of(node)
        if template is None:
            continue
        node_type = node.get("data", {}).get("type")

        for field, target in targets:
            if node_type != target.component_type or field.name not in config:
                continue
            entry = template.get(target.input_name)
            # An input the component does not declare is not ours to add.
            if not isinstance(entry, dict):
                continue
            value = config[field.name]
            if entry.get("value") == value:
                continue
            entry["value"] = value
            written += 1

    return ConfigWrite(data=updated if written else flow_data, inputs_written=written)
