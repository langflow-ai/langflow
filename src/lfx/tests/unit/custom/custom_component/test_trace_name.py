"""Regression tests for CustomComponent.trace_name resolution.

Covers the trace_display_name override and UI node-rename propagation
requested in https://github.com/langflow-ai/langflow/issues/7284.
"""

from types import SimpleNamespace

import pytest
from lfx.custom.custom_component.component import Component
from lfx.custom.custom_component.custom_component import CustomComponent


class TracedComponent(Component):
    display_name = "X"


def test_default_trace_name_with_id():
    component = CustomComponent(display_name="X", _id="X-abc123")
    assert component.trace_name == "X (X-abc123)"


def test_default_trace_name_without_id():
    component = CustomComponent(display_name="X")
    assert component.trace_name == "X"


def test_trace_name_raises_when_id_is_none():
    component = CustomComponent(display_name="X", _id=None)
    with pytest.raises(ValueError, match="Component id is not set"):
        _ = component.trace_name


def test_explicit_override_is_used():
    component = CustomComponent(display_name="X", _id="X-abc123", trace_display_name="RAG Query")
    assert component.trace_name == "RAG Query (X-abc123)"


def test_blank_override_falls_back_to_default():
    component = CustomComponent(display_name="X", _id="X-abc123", trace_display_name="   ")
    assert component.trace_name == "X (X-abc123)"


def test_non_string_override_falls_back_to_default():
    component = CustomComponent(display_name="X", _id="X-abc123", trace_display_name=123)
    assert component.trace_name == "X (X-abc123)"


def test_direct_assignment_override():
    component = TracedComponent()
    component.trace_display_name = "Direct Name"
    assert component.trace_name.startswith("Direct Name (")


def test_ctor_kwarg_override_resolved_through_component_attributes():
    component = TracedComponent(trace_display_name="Kwarg Name")
    assert component.trace_name.startswith("Kwarg Name (")


def test_stripped_override_is_normalized():
    component = CustomComponent(display_name="X", _id="X-abc123", trace_display_name="  RAG Query  ")
    assert component.trace_name == "RAG Query (X-abc123)"


def test_vertex_rename_propagates():
    component = CustomComponent(display_name="X", _id="abc123-def456")
    component._vertex = SimpleNamespace(display_name="Renamed Node", id="abc123-def456")
    assert component.trace_name == "Renamed Node (abc123-def456)"


def test_vertex_id_fragment_guard_falls_back_to_class_display_name():
    component = CustomComponent(display_name="X", _id="b62c8e1e-9999")
    component._vertex = SimpleNamespace(display_name="b62c8e1e", id="b62c8e1e-9999")
    assert component.trace_name == "X (b62c8e1e-9999)"


def test_vertex_name_equal_to_class_display_name_is_byte_identical():
    component = CustomComponent(display_name="X", _id="X-abc123")
    default = component.trace_name
    component._vertex = SimpleNamespace(display_name="X", id="vertex-999")
    assert component.trace_name == default


def test_explicit_override_wins_over_vertex_rename():
    component = CustomComponent(display_name="X", _id="abc123-def456")
    component._vertex = SimpleNamespace(display_name="Renamed Node", id="abc123-def456")
    component.trace_display_name = "Explicit"
    assert component.trace_name == "Explicit (abc123-def456)"


def test_same_override_yields_unique_trace_names_across_instances():
    first = CustomComponent(display_name="X", _id="X-id1", trace_display_name="Shared")
    second = CustomComponent(display_name="X", _id="X-id2", trace_display_name="Shared")
    assert first.trace_name == "Shared (X-id1)"
    assert second.trace_name == "Shared (X-id2)"
    assert first.trace_name != second.trace_name
