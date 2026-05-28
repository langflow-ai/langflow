"""User-reviewable edit proposals (JSON-Patch-validated, no auto-apply).

``ProposeFieldEdit`` is the only tool here today: it validates a field-value
change against the working flow with a JSON-Patch dry run and emits an
``edit_field`` event so the frontend can render a Continue/Dismiss card.
Nothing is applied to the canvas until the user accepts.
"""

from __future__ import annotations

import copy
import uuid

import jsonpatch

from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema import Data

from ._state import _emit, _find_node, _readable_preview, get_working_flow


def emit_field_edit_proposal(flow: dict, component_id: str, field_name: str, new_value: object) -> bool:
    """Emit a reviewable ``edit_field`` event for one field — the configure→propose bridge.

    Produces the SAME ``edit_field`` payload shape as ``ProposeFieldEdit`` (id,
    component_id, component_type, field, old_value, new_value, description, JSON
    Patch) so the frontend carousel renders it identically. Returns True when a
    proposal was emitted; False when the node/field could not be resolved, so
    the caller can fall back to a direct apply.
    """
    node = _find_node(flow, component_id)
    if node is None:
        return False
    template = node.get("data", {}).get("node", {}).get("template", {})
    if field_name not in template or not isinstance(template.get(field_name), dict):
        return False
    old_value = template[field_name].get("value")

    node_idx = None
    for i, n in enumerate(flow.get("data", {}).get("nodes", [])):
        nid = n.get("data", {}).get("id", n.get("id", ""))
        if nid == component_id:
            node_idx = i
            break
    if node_idx is None:
        return False

    path = f"/data/nodes/{node_idx}/data/node/template/{field_name}/value"
    patch_ops = [{"op": "replace", "path": path, "value": new_value}]
    component_type = node.get("data", {}).get("type", "?")
    _emit(
        "edit_field",
        id=str(uuid.uuid4())[:8],
        component_id=component_id,
        component_type=component_type,
        field=field_name,
        old_value=old_value,
        new_value=new_value,
        description=f'Set {field_name} to "{_readable_preview(new_value)}" on {component_type}',
        patch=patch_ops,
    )
    return True


class ProposeFieldEdit(Component):
    display_name = "Propose Field Edit"
    description = "Propose a field value change on a component. Validates and generates a reviewable patch."
    icon = "Pencil"
    name = "ProposeFieldEdit"

    inputs = [
        MessageTextInput(
            name="component_id",
            display_name="Component ID",
            info="Full component ID (e.g. 'OpenAIModel-x3Y4z').",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="field_name",
            display_name="Field Name",
            info="The field to change (e.g. 'model_name', 'temperature').",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="new_value",
            display_name="New Value",
            info="The new value to set.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="propose_field_edit"),
    ]

    def propose_field_edit(self) -> Data:
        flow = get_working_flow()
        if flow is None:
            return Data(data={"error": "No flow loaded. Cannot propose edits on an empty canvas."})

        # 1. Find the node
        node = _find_node(flow, self.component_id)
        if node is None:
            available = [n.get("data", {}).get("id", "") for n in flow.get("data", {}).get("nodes", [])]
            return Data(
                data={
                    "error": f"Component '{self.component_id}' not found. Available: {available}",
                }
            )

        # 2. Validate field exists
        template = node.get("data", {}).get("node", {}).get("template", {})
        if self.field_name not in template or not isinstance(template.get(self.field_name), dict):
            available = [k for k, v in template.items() if isinstance(v, dict) and k not in ("code", "_type")]
            return Data(
                data={
                    "error": f"Field '{self.field_name}' not found on '{self.component_id}'. Available: {available}",
                }
            )

        # 3. Read old value
        old_value = template[self.field_name].get("value")

        # 4. Resolve node index
        node_idx = None
        for i, n in enumerate(flow.get("data", {}).get("nodes", [])):
            nid = n.get("data", {}).get("id", n.get("id", ""))
            if nid == self.component_id:
                node_idx = i
                break

        if node_idx is None:
            return Data(data={"error": f"Could not resolve index for '{self.component_id}'"})

        # 5. Build JSON Patch
        path = f"/data/nodes/{node_idx}/data/node/template/{self.field_name}/value"
        patch_ops = [{"op": "replace", "path": path, "value": self.new_value}]

        # 6. Dry run -- apply to a copy
        try:
            patch = jsonpatch.JsonPatch(patch_ops)
            patched = patch.apply(copy.deepcopy(flow))
            # Verify the value actually changed
            patched_node = patched["data"]["nodes"][node_idx]
            patched_val = patched_node["data"]["node"]["template"][self.field_name]["value"]
            if patched_val != self.new_value:
                return Data(data={"error": "Patch dry run: value did not change as expected"})
        except (jsonpatch.JsonPatchException, KeyError, IndexError) as e:
            return Data(data={"error": f"Patch validation failed: {e}"})

        # 7. Emit flow_action event
        component_type = node.get("data", {}).get("type", "?")
        action_id = str(uuid.uuid4())[:8]
        _emit(
            "edit_field",
            id=action_id,
            component_id=self.component_id,
            component_type=component_type,
            field=self.field_name,
            old_value=old_value,
            new_value=self.new_value,
            description=f'Set {self.field_name} to "{_readable_preview(self.new_value)}" on {component_type}',
            patch=patch_ops,
        )

        preview = _readable_preview(self.new_value)
        text = f'Proposed: set {self.field_name} = "{preview}" on {component_type} (pending user approval)'
        return Data(data={"text": text})
