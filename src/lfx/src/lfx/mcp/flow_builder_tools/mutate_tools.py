"""Graph-mutation tools (add/remove/connect/configure components).

Every mutation pushes a ``flow_update`` event via ``_emit`` so the
assistant service can stream it back to the canvas. Tools here are the
ones whose effects the user sees on the canvas immediately.
"""

from __future__ import annotations

import json

from lfx.custom import Component
from lfx.graph.flow_builder.component import add_component as fb_add_component
from lfx.graph.flow_builder.component import configure_component as fb_configure
from lfx.graph.flow_builder.component import remove_component as fb_remove_component
from lfx.graph.flow_builder.connect import add_connection as fb_add_connection
from lfx.graph.flow_builder.layout import layout_flow
from lfx.io import MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema import Data

from ._state import (
    _emit,
    _ensure_working_flow,
    _find_node,
    _load_registry_user_aware,
    node_existed_at_start,
    should_propose_existing_edits,
)
from .edit_tools import emit_field_edit_proposal


class AddComponent(Component):
    display_name = "Add Component"
    description = "Add a component to the user's flow canvas. Returns the component's id."
    icon = "Plus"
    name = "AddComponent"

    inputs = [
        MessageTextInput(
            name="component_type",
            display_name="Component Type",
            info="Component type name (e.g. 'ChatInput', 'OpenAIModel'). Use search_components to find types.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="add_component"),
    ]

    def add_component(self) -> Data:
        registry = _load_registry_user_aware()
        flow = _ensure_working_flow()
        try:
            result = fb_add_component(flow, self.component_type, registry)
            layout_flow(flow)
            _emit("add_component", node=flow["data"]["nodes"][-1])
            text = f"Added {self.component_type} ({result['id']})"
            return Data(data={"id": result["id"], "type": self.component_type, "text": text})
        except (ValueError, KeyError) as e:
            logger.warning("add_component failed: %s", e)
            return Data(data={"error": str(e)})


class RemoveComponent(Component):
    display_name = "Remove Component"
    description = "Remove a component and its connections from the flow."
    icon = "Trash2"
    name = "RemoveComponent"

    inputs = [
        MessageTextInput(
            name="component_id",
            display_name="Component ID",
            info="The component ID to remove (e.g. 'ChatInput-a1B2c').",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="remove_component"),
    ]

    def remove_component(self) -> Data:
        flow = _ensure_working_flow()
        try:
            fb_remove_component(flow, self.component_id)
            layout_flow(flow)
            _emit("remove_component", component_id=self.component_id)
            return Data(data={"removed": self.component_id, "text": f"Removed {self.component_id}"})
        except (ValueError, KeyError) as e:
            logger.warning("remove_component failed: %s", e)
            return Data(data={"error": str(e)})


def _sync_model_input_connection_mode(flow: dict, target_id: str, target_input: str) -> None:
    """Flip ``_connectionMode`` on a model-input target so the canvas renders the edge.

    Why: ModelInput targets (``type='model'``) render an inline dropdown by default.
    The "Connect other models" UX switches the field to connection mode by setting
    ``_connectionMode=true`` on the node — only THEN does the left handle accept
    an external model edge visibly. Mirror that flag at connect time, otherwise
    the edge exists in state but the dropdown still hides it.
    """
    target_node = _find_node(flow, target_id)
    if target_node is None:
        return
    target_template = target_node.get("data", {}).get("node", {}).get("template", {})
    target_field = target_template.get(target_input) or {}
    if not (isinstance(target_field, dict) and target_field.get("type") == "model"):
        return
    target_node["data"]["_connectionMode"] = True
    _emit("set_connection_mode", component_id=target_id, enabled=True)


def _emit_source_tool_mode_if_flipped(flow: dict, source_id: str, source_output: str) -> None:
    """Tell the canvas the source node was flipped to tool mode on connect.

    When connecting ``X.component_as_tool -> Agent.tools``, ``add_connection``
    flips X into tool mode IN THE WORKING FLOW: its outputs collapse to the
    single synthesized ``component_as_tool`` (Toolset) output. The ``connect``
    event only carries the EDGE — it never surfaces X's new outputs. Without
    this, the canvas keeps rendering X's OLD output, the edge's
    ``component_as_tool`` source handle has no matching handle on the node, and
    the edge silently fails to render — the "says it connected but didn't" bug.
    Emit the flipped node's outputs so the frontend re-renders X in tool mode
    and the edge can attach.
    """
    if source_output != "component_as_tool":
        return
    node = _find_node(flow, source_id)
    if node is None:
        return
    inner = node.get("data", {}).get("node", {})
    if not inner.get("tool_mode"):
        return
    _emit("enable_tool_mode", component_id=source_id, outputs=inner.get("outputs", []))


def _reconcile_source_selected_output(flow: dict, source_id: str, source_output: str) -> None:
    """Mirror the connected output as the source node's ``selected_output``.

    Why: the frontend reads ``data.selected_output`` (top-level on the ReactFlow
    node) to decide which output handle is rendered for components with multiple
    outputs. Without this the edge exists but the node label stays on the
    default output, looking unconnected. For a single/zero-output source, also
    reconcile a stale ``selected_output`` left by a prior wiring.
    """
    source_node = _find_node(flow, source_id)
    if source_node is None:
        return
    outputs = source_node.get("data", {}).get("node", {}).get("outputs", [])
    if len(outputs) > 1:
        source_node["data"]["selected_output"] = source_output
        _emit("select_output", component_id=source_id, output_name=source_output)
        return
    # Single/zero output (e.g. tool-mode collapsed them): a leftover
    # selected_output from a prior wiring would point at a removed output.
    output_names = {o.get("name") for o in outputs if isinstance(o, dict)}
    stale = source_node["data"].get("selected_output")
    if stale is None or stale in output_names:
        return
    source_node["data"].pop("selected_output", None)
    if outputs:
        _emit("select_output", component_id=source_id, output_name=outputs[0].get("name", ""))


class ConnectComponents(Component):
    display_name = "Connect Components"
    description = "Connect an output of one component to an input of another."
    icon = "Link"
    name = "ConnectComponents"

    inputs = [
        MessageTextInput(name="source_id", display_name="Source ID", required=True, tool_mode=True),
        MessageTextInput(name="source_output", display_name="Source Output", required=True, tool_mode=True),
        MessageTextInput(name="target_id", display_name="Target ID", required=True, tool_mode=True),
        MessageTextInput(name="target_input", display_name="Target Input", required=True, tool_mode=True),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="connect_components"),
    ]

    def connect_components(self) -> Data:
        # B3: model-input mirroring + selected-output reconciliation live in
        # module-private helpers above so this orchestrator stays flat (CC ≤ 3).
        flow = _ensure_working_flow()
        try:
            fb_add_connection(flow, self.source_id, self.source_output, self.target_id, self.target_input)
            layout_flow(flow)
            _sync_model_input_connection_mode(flow, self.target_id, self.target_input)
            # Flip tool-mode BEFORE emitting the edge, else the source node has
            # no `component_as_tool` handle yet and the edge never attaches.
            _emit_source_tool_mode_if_flipped(flow, self.source_id, self.source_output)
            edge = flow["data"]["edges"][-1]
            _emit("connect", edge=edge)
            _reconcile_source_selected_output(flow, self.source_id, self.source_output)
            return Data(
                data={
                    "text": f"Connected {self.source_id}.{self.source_output} -> {self.target_id}.{self.target_input}",
                }
            )
        except (ValueError, KeyError) as e:
            logger.warning("connect_components failed: %s", e)
            return Data(data={"error": str(e)})


class ConfigureComponent(Component):
    display_name = "Configure Component"
    description = "Set one or more parameters on a component. Pass a JSON dict for multiple params at once."
    icon = "Settings"
    name = "ConfigureComponent"

    inputs = [
        MessageTextInput(name="component_id", display_name="Component ID", required=True, tool_mode=True),
        MessageTextInput(
            name="params",
            display_name="Parameters",
            info='JSON dict of params to set, e.g. \'{"model_name": "gpt-4o", "temperature": 0.7}\'',
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="configure_component"),
    ]

    def configure_component(self) -> Data:
        flow = _ensure_working_flow()

        # Accept params as dict (from tool framework) or JSON string
        raw = self.params
        if isinstance(raw, dict):
            params = raw
        else:
            raw = (raw or "").strip()
            try:
                params = json.loads(raw)
                if not isinstance(params, dict):
                    return Data(data={"error": f"params must be a JSON object, got {type(params).__name__}"})
            except json.JSONDecodeError:
                return Data(data={"error": f'Invalid JSON in params: {raw!r}. Use format: {{"key": "value"}}'})

        # Deterministic review gate (Bug B): editing a TEXT field on a pre-existing
        # component is surfaced as a reviewable diff; model/number/bool still apply live.
        if should_propose_existing_edits() and node_existed_at_start(self.component_id):
            text_params = {k: v for k, v in params.items() if isinstance(v, str) and k != "model"}
            if text_params:
                proposed: list[str] = [
                    k for k, v in text_params.items() if emit_field_edit_proposal(flow, self.component_id, k, v)
                ]
                remaining = {k: v for k, v in params.items() if k not in proposed}
                if remaining:
                    try:
                        fb_configure(flow, self.component_id, remaining)
                        _fill_missing_model_names(flow, self.component_id, remaining)
                        _mirror_model_value_into_options(flow, self.component_id, remaining)
                        _emit("configure", component_id=self.component_id, params=remaining)
                    except (ValueError, KeyError) as e:
                        logger.warning("configure_component (non-text remainder) failed: %s", e)
                        return Data(data={"error": str(e)})
                if proposed:
                    fields = ", ".join(proposed)
                    return Data(
                        data={
                            "text": f"Proposed changes to {fields} on {self.component_id} (pending user approval)",
                            "proposed": proposed,
                        }
                    )

        try:
            # fb_configure normalizes the model spec (JSON/YAML/dict/list) in place;
            # the fill + mirror steps below then read the canonical list[dict].
            fb_configure(flow, self.component_id, params)
            # Provider-only selections get the catalog default name, then mirror
            # into `options` so the dropdown matches instead of its own fallback.
            _fill_missing_model_names(flow, self.component_id, params)
            _mirror_model_value_into_options(flow, self.component_id, params)
            _emit("configure", component_id=self.component_id, params=params)
            summary = ", ".join(f"{k}={v!r}" for k, v in params.items())
            return Data(data={"text": f"Set {summary} on {self.component_id}", "configured": list(params.keys())})
        except (ValueError, KeyError) as e:
            logger.warning("configure_component failed: %s", e)
            return Data(data={"error": str(e)})


def _mirror_model_value_into_options(flow: dict, component_id: str, params: dict) -> None:
    """Mirror the new ModelInput selection into the field's `options` array.

    For each ModelInput field touched in `params`, ensure the new selection
    is present in the field's `options` array. No-op for non-model fields.
    Idempotent: existing entries with the same name+provider are not
    duplicated.
    """
    node = _find_node(flow, component_id)
    if node is None:
        return
    template = node.get("data", {}).get("node", {}).get("template", {})
    for field_name, value in params.items():
        field = template.get(field_name)
        if not isinstance(field, dict) or field.get("type") != "model":
            continue
        if not isinstance(value, list) or not value:
            continue
        first = value[0]
        if not isinstance(first, dict):
            continue
        new_name = first.get("name")
        new_provider = first.get("provider")
        if not new_name:
            continue
        options = field.get("options") or []
        if any(
            isinstance(o, dict) and o.get("name") == new_name and o.get("provider") == new_provider for o in options
        ):
            continue
        options.append({"name": new_name, "provider": new_provider})
        field["options"] = options


def _resolve_default_model_name(provider: str) -> str | None:
    """Return the provider's catalog default model name, or None if unknown."""
    from lfx.base.models.unified_models import get_unified_models_detailed

    detailed = get_unified_models_detailed(
        providers=[provider],
        only_defaults=True,
        include_unsupported=False,
        include_deprecated=False,
    )
    for entry in detailed:
        for model in entry.get("models", []):
            name = model.get("model_name")
            if name:
                return name
    return None


def _fill_missing_model_names(flow: dict, component_id: str, params: dict) -> None:
    """Fill a provider-only model selection with the provider's default model.

    A bare ``[{"provider": X}]`` (no name) otherwise leaves the canvas dropdown
    to silently pick the provider's newest model, diverging from what the
    assistant reported. Resolving the default keeps value, options and the
    result text on the same concrete model. ``params`` shares the value object
    set by ``fb_configure``, so mutating it updates the node template too.
    """
    node = _find_node(flow, component_id)
    if node is None:
        return
    template = node.get("data", {}).get("node", {}).get("template", {})
    for field_name, value in params.items():
        field = template.get(field_name)
        if not isinstance(field, dict) or field.get("type") != "model":
            continue
        if not isinstance(value, list) or not value or not isinstance(value[0], dict):
            continue
        entry = value[0]
        if entry.get("name") or not entry.get("provider"):
            continue
        default_name = _resolve_default_model_name(entry["provider"])
        if default_name:
            entry["name"] = default_name
