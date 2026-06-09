"""Bug #6 (PR-12575): assistant-built generated components show a bogus "Update available" badge.

A component the assistant GENERATES (e.g. ``RestaurantMenuTool``) lands in the
user's overlay registry keyed by its class name. When the assistant then adds
it to a flow, ``_make_node`` stamped the canvas node's ``data.type`` with that
class name. The frontend's outdated/blocked detector (``check-code-validity.ts``)
looks the type up in the global ``/all`` template list -- which never contains
user sandbox components -- so the node has code but no matching template
(``blocked``), and the canvas paints the "Update available" badge.

A custom component added the normal way (sidebar "Custom Component", or the
assistant's own generate_component card) uses ``data.type == "CustomComponent"``,
which IS in the global templates AND in ``componentsToIgnoreUpdate`` -- so it
never shows the badge. The flow-builder path must do the same: emit user
(overlay) components as ``CustomComponent``.

These tests assert the emitted node TYPE -- the exact value the frontend keys on.
"""

from __future__ import annotations

from lfx.graph.flow_builder.component import add_component


def _entry(display_name: str) -> dict:
    return {
        "display_name": display_name,
        "template": {"code": {"value": "class X: ..."}},
        "outputs": [],
    }


def _empty_flow() -> dict:
    return {"data": {"nodes": [], "edges": []}}


class TestUserGeneratedComponentNodeType:
    def test_should_emit_custom_component_type_when_entry_is_user_generated(self):
        # GIVEN a user-overlay (generated) entry, marked custom.
        registry = {"RestaurantMenuTool": {**_entry("Restaurant Menu Tool"), "custom": True}}
        flow = _empty_flow()

        add_component(flow, "RestaurantMenuTool", registry)

        node = flow["data"]["nodes"][-1]
        # The frontend keys the badge off data.type; it must be the canonical
        # custom-component type so the type resolves in the global templates.
        assert node["data"]["type"] == "CustomComponent"

    def test_should_preserve_real_template_and_strip_internal_marker(self):
        registry = {"RestaurantMenuTool": {**_entry("Restaurant Menu Tool"), "custom": True}}
        flow = _empty_flow()

        add_component(flow, "RestaurantMenuTool", registry)

        node = flow["data"]["nodes"][-1]
        # The real template (code, display name) is preserved...
        assert node["data"]["node"]["display_name"] == "Restaurant Menu Tool"
        assert node["data"]["node"]["template"]["code"]["value"] == "class X: ..."
        # ...and the internal 'custom' marker is not leaked onto the canvas node
        # (real CustomComponent entries carry no such top-level key).
        assert "custom" not in node["data"]["node"]

    def test_should_keep_own_type_for_base_builtin_component(self):
        # Regression guard: built-ins must NOT be relabelled.
        registry = {"ChatInput": _entry("Chat Input")}
        flow = _empty_flow()

        add_component(flow, "ChatInput", registry)

        node = flow["data"]["nodes"][-1]
        assert node["data"]["type"] == "ChatInput"
