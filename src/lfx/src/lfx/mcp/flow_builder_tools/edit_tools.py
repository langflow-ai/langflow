"""User-reviewable edit proposals (JSON-Patch-validated, no auto-apply).

``ProposeFieldEdit`` is the only tool here today: it validates a field-value
change against the working flow with a JSON-Patch dry run and emits an
``edit_field`` event so the frontend can render a Continue/Dismiss card.
Nothing is applied to the canvas until the user accepts.
"""

from __future__ import annotations

import copy
import json
import uuid

import jsonpatch

from lfx.custom import Component
from lfx.graph.flow_builder.component import validate_router_mode_update
from lfx.io import MessageTextInput, Output
from lfx.schema import Data
from lfx.services.model_provider_policy import ModelProviderPolicyError

from ._state import (
    _emit,
    _find_node,
    _readable_preview,
    emit_tool_start,
    get_working_flow,
    should_apply_edits_live,
)


def _prepare_field_edit_proposal(flow: dict, component_id: str, field_name: str, new_value: object) -> dict | None:
    """Validate and build one reviewable field-edit payload without emitting it."""
    node = _find_node(flow, component_id)
    if node is None:
        return None
    template = node.get("data", {}).get("node", {}).get("template", {})
    if field_name not in template or not isinstance(template.get(field_name), dict):
        return None
    old_value = template[field_name].get("value")
    new_value = _normalize_field_replacement(field_name, old_value, new_value)

    node_idx = None
    for i, n in enumerate(flow.get("data", {}).get("nodes", [])):
        nid = n.get("data", {}).get("id", n.get("id", ""))
        if nid == component_id:
            node_idx = i
            break
    if node_idx is None:
        return None

    path = f"/data/nodes/{node_idx}/data/node/template/{field_name}/value"
    component_type = node.get("data", {}).get("type", "?")
    return {
        "id": str(uuid.uuid4())[:8],
        "component_id": component_id,
        "component_type": component_type,
        "field": field_name,
        "old_value": old_value,
        "new_value": new_value,
        "description": f'Set {field_name} to "{_readable_preview(new_value)}" on {component_type}',
        "patch": [{"op": "replace", "path": path, "value": new_value}],
    }


def emit_field_edit_proposal(flow: dict, component_id: str, field_name: str, new_value: object) -> bool:
    """Emit a reviewable ``edit_field`` event for one field — the configure→propose bridge.

    Produces the SAME ``edit_field`` payload shape as ``ProposeFieldEdit`` (id,
    component_id, component_type, field, old_value, new_value, description, JSON
    Patch) so the frontend carousel renders it identically. Returns True when a
    proposal was emitted; False when the node/field could not be resolved, so
    the caller can fall back to a direct apply.
    """
    proposal = _prepare_field_edit_proposal(flow, component_id, field_name, new_value)
    if proposal is None:
        return False
    _emit("edit_field", **proposal)
    return True


def _validate_tool_metadata_edit(edit: dict) -> None:
    """Validate known tool metadata fields while allowing future metadata keys."""
    string_fields = ("name", "description", "display_name", "display_description")
    for field in string_fields:
        if field in edit and not isinstance(edit[field], str):
            msg = f"tools_metadata field '{field}' must be a string"
            raise TypeError(msg)

    if "tags" in edit and (
        not isinstance(edit["tags"], list) or not edit["tags"] or not all(isinstance(tag, str) for tag in edit["tags"])
    ):
        msg = "tools_metadata field 'tags' must be a non-empty array of strings"
        raise TypeError(msg)
    if "status" in edit and not isinstance(edit["status"], bool):
        msg = "tools_metadata field 'status' must be a boolean"
        raise TypeError(msg)
    if "approval_actions" in edit and (
        not isinstance(edit["approval_actions"], list)
        or not all(isinstance(action, str) for action in edit["approval_actions"])
    ):
        msg = "tools_metadata field 'approval_actions' must be an array of strings"
        raise TypeError(msg)
    if "readonly" in edit and not isinstance(edit["readonly"], bool):
        msg = "tools_metadata field 'readonly' must be a boolean"
        raise TypeError(msg)
    if "args" in edit and not isinstance(edit["args"], dict):
        msg = "tools_metadata field 'args' must be an object"
        raise TypeError(msg)


def _merge_tool_metadata_edits(current_value: list, proposed_value: object) -> list:
    """Merge validated tool-row updates using the stable first tag as identity."""
    if not current_value or not all(isinstance(row, dict) for row in current_value):
        msg = "Field 'tools_metadata' must contain at least one valid tool row"
        raise ValueError(msg)

    if isinstance(proposed_value, dict):
        edits = [proposed_value]
    elif isinstance(proposed_value, list) and proposed_value:
        edits = proposed_value
    else:
        msg = "Field 'tools_metadata' expects a tool object or a non-empty array of tool objects"
        raise ValueError(msg)

    if not all(isinstance(edit, dict) for edit in edits):
        msg = "Field 'tools_metadata' expects every proposed tool edit to be an object"
        raise ValueError(msg)

    merged = copy.deepcopy(current_value)
    used_indices: set[int] = set()
    for edit in edits:
        _validate_tool_metadata_edit(edit)
        if not edit or set(edit) == {"tags"}:
            msg = "Each tools_metadata edit must change at least one metadata field"
            raise ValueError(msg)

        if "tags" in edit:
            identity = edit["tags"][0]
            matching_indices = [
                index
                for index, row in enumerate(current_value)
                if isinstance(row.get("tags"), list) and row["tags"] and row["tags"][0] == identity
            ]
        elif len(current_value) == 1 and len(edits) == 1:
            matching_indices = [0]
        else:
            matching_indices = []

        if len(matching_indices) != 1:
            msg = (
                "Could not identify exactly one tools_metadata row for the metadata edit. "
                "Provide the existing tool's first tag when the field contains multiple rows."
            )
            raise ValueError(msg)

        target_index = matching_indices[0]
        if target_index in used_indices:
            target_tags = current_value[target_index].get("tags") or []
            target_identity = target_tags[0] if target_tags else ""
            msg = f"Multiple tools_metadata edits target the same tool row '{target_identity}'"
            raise ValueError(msg)

        merged[target_index].update(copy.deepcopy(edit))
        used_indices.add(target_index)

    return merged


def _normalize_field_replacement(field_name: str, current_value: object, proposed_value: object) -> object:
    """Normalize tools_metadata proposals without changing unrelated fields."""
    if field_name != "tools_metadata":
        return proposed_value

    if not isinstance(current_value, list):
        msg = "Field 'tools_metadata' must currently be an array"
        raise TypeError(msg)

    parsed_value = proposed_value
    if isinstance(proposed_value, str):
        try:
            parsed_value = json.loads(proposed_value)
        except json.JSONDecodeError as exc:
            msg = f"Field '{field_name}' expects valid JSON because its current value is structured: {exc.msg}"
            raise ValueError(msg) from exc

    return _merge_tool_metadata_edits(current_value, parsed_value)


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
        emit_tool_start("propose_field_edit", component_id=self.component_id, field=self.field_name)
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

        # 3. Read and normalize the prospective value before either the UI or
        # a headless caller can apply it.
        old_value = template[self.field_name].get("value")
        try:
            new_value = _normalize_field_replacement(self.field_name, old_value, self.new_value)
        except (TypeError, ValueError) as exc:
            return Data(data={"error": str(exc)})

        # This tool is an alternate configuration path: the UI may apply its
        # emitted patch after approval, while headless callers apply it below.
        # Gate the normalized prospective value before either mutation can escape.
        from .mutate_tools import _model_providers_in_params, _require_allowed_model_providers

        try:
            prospective_params = {self.field_name: new_value}
            _require_allowed_model_providers(_model_providers_in_params(flow, self.component_id, prospective_params))
            if node["data"].get("type") == "SmartRouter":
                validate_router_mode_update(template, prospective_params)
        except (ModelProviderPolicyError, ValueError) as exc:
            return Data(data={"error": str(exc)})

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
        patch_ops = [{"op": "replace", "path": path, "value": new_value}]

        # 6. Dry run -- apply to a copy
        try:
            patch = jsonpatch.JsonPatch(patch_ops)
            patched = patch.apply(copy.deepcopy(flow))
            # Verify the value actually changed
            patched_node = patched["data"]["nodes"][node_idx]
            patched_val = patched_node["data"]["node"]["template"][self.field_name]["value"]
            if patched_val != new_value:
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
            new_value=new_value,
            description=f'Set {self.field_name} to "{_readable_preview(new_value)}" on {component_type}',
            patch=patch_ops,
        )

        preview = _readable_preview(new_value)
        # Headless callers have no review UI; apply live and narrate as done so the
        # assistant never claims a pending-approval step that cannot happen (#13641).
        if should_apply_edits_live():
            template[self.field_name]["value"] = new_value
            return Data(data={"text": f'Set {self.field_name} = "{preview}" on {component_type}'})

        text = f'Proposed: set {self.field_name} = "{preview}" on {component_type} (pending user approval)'
        return Data(data={"text": text})
