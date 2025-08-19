from unittest.mock import Mock

import pytest
from langflow.components.custom_component import CustomComponent


@pytest.fixture
def mock_vertex():
    vertex = Mock()
    vertex.get_node_property = Mock(
        side_effect=lambda key, default: {
            "display_name": "Mock Vertex Display Name",
            "description": "Mock Vertex Description",
        }.get(key, default)
    )
    return vertex


@pytest.fixture
def custom_component_with_vertex(mock_vertex):
    component = CustomComponent()
    component._vertex = mock_vertex
    component.display_name = "Default Display Name"
    component.description = "Default Description"
    return component


@pytest.fixture
def custom_component_without_vertex():
    component = CustomComponent()
    component.display_name = "Default Display Name"
    component.description = "Default Description"
    return component


def test_effective_display_name_with_vertex(custom_component_with_vertex):
    assert custom_component_with_vertex.effective_display_name == "Mock Vertex Display Name", (
        "Effective display name should be fetched from the vertex when available."
    )


def test_effective_display_name_without_vertex(custom_component_without_vertex):
    assert custom_component_without_vertex.effective_display_name == "Default Display Name", (
        "Effective display name should fallback to the component's default when vertex is not set."
    )


def test_effective_description_with_vertex(custom_component_with_vertex):
    assert custom_component_with_vertex.effective_description == "Mock Vertex Description", (
        "Effective description should be fetched from the vertex when available."
    )


def test_effective_description_without_vertex(custom_component_without_vertex):
    assert custom_component_without_vertex.effective_description == "Default Description", (
        "Effective description should fallback to the component's default when vertex is not set."
    )
