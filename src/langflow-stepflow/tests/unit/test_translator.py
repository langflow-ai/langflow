"""Unit tests for LangflowConverter."""

from typing import Any

import pytest

from langflow_stepflow.exceptions import ConversionError
from langflow_stepflow.translation.translator import LangflowConverter


def unwrap_value(value: Any) -> Any:
    """Recursively unwrap ValueExpr/PrimitiveValue to get the raw value."""
    if value is None:
        return None
    # Unwrap ValueExpr and PrimitiveValue
    if hasattr(value, "actual_instance"):
        return unwrap_value(value.actual_instance)
    # Recursively unwrap dicts
    if isinstance(value, dict):
        return {k: unwrap_value(v) for k, v in value.items()}
    # Recursively unwrap lists
    if isinstance(value, list):
        return [unwrap_value(v) for v in value]
    return value


def get_step_input_dict(step) -> dict:
    """Extract the input dict from a step's ValueExpr wrapper.

    The Step.input field is a Pydantic ValueExpr oneOf wrapper. This helper
    unwraps it to get the underlying dict for assertions.
    """
    if step.input is None:
        return {}
    return unwrap_value(step.input)


class TestLangflowConverter:
    """Test LangflowConverter functionality."""

    def test_init_default(self):
        """Test default initialization."""
        converter = LangflowConverter()

    def test_convert_simple_workflow(self, converter: LangflowConverter, simple_langflow_workflow: dict[str, Any]):
        """Test conversion of simple workflow."""
        workflow = converter.convert(simple_langflow_workflow)

        assert workflow.name == "Converted Langflow Workflow"

        # ChatInput and ChatOutput are I/O connection points, not processing steps
        # They handle Message type conversion but don't create workflow steps
        assert len(workflow.steps) == 0

        # Verify the workflow structure is valid (Flow is a proper object)
        assert workflow is not None

        # Workflow should have output that references input (passthrough)
        assert workflow.output is not None

    def test_convert_empty_nodes(self, converter: LangflowConverter):
        """Test conversion with empty nodes list."""
        workflow_data = {"data": {"nodes": [], "edges": []}}

        with pytest.raises(ConversionError, match="No nodes found"):
            converter.convert(workflow_data)

    def test_convert_missing_data(self, converter: LangflowConverter):
        """Test conversion with missing data key."""
        workflow_data = {"invalid": "structure"}

        with pytest.raises(ConversionError, match="missing 'data' key"):
            converter.convert(workflow_data)

    def test_to_yaml(self, converter: LangflowConverter, simple_langflow_workflow: dict[str, Any]):
        """Test YAML generation."""
        workflow = converter.convert(simple_langflow_workflow)
        yaml_output = converter.to_yaml(workflow)

        assert isinstance(yaml_output, str)
        assert "name: Converted Langflow Workflow" in yaml_output
        # Should have output section since ChatInput/ChatOutput create passthrough
        assert "output:" in yaml_output

    def test_analyze_workflow(self, converter: LangflowConverter, simple_langflow_workflow: dict[str, Any]):
        """Test workflow analysis."""
        analysis = converter.analyze(simple_langflow_workflow)

        assert analysis.node_count == 2
        assert analysis.edge_count == 1
        assert "ChatInput" in analysis.component_types
        assert "ChatOutput" in analysis.component_types

    def test_step_ordering_with_dependencies(self, converter: LangflowConverter):
        """Test that steps are ordered based on dependencies, not node order."""
        # Create workflow with intentionally wrong node order
        trivial_code = """
from langflow.custom.custom_component.component import Component
from langflow.io import Output

class TrivialComponent(Component):
    outputs = [Output(display_name="Output", name="output", method="build")]

    def build(self) -> str:
        return "trivial result"
"""

        workflow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "output-node",  # This depends on others but appears first
                        "data": {
                            "type": "TrivialOutput",
                            "node": {
                                "template": {"code": {"value": trivial_code}},
                                "outputs": [{"name": "output", "method": "build"}],
                            },
                        },
                        "type": "genericNode",
                    },
                    {
                        "id": "input-node",  # This has no dependencies but appears last
                        "data": {
                            "type": "TrivialInput",
                            "node": {
                                "template": {"code": {"value": trivial_code}},
                                "outputs": [{"name": "output", "method": "build"}],
                            },
                        },
                        "type": "genericNode",
                    },
                    {
                        "id": "middle-node",  # This depends on input but appears middle
                        "data": {
                            "type": "TrivialMiddle",
                            "node": {
                                "template": {"code": {"value": trivial_code}},
                                "outputs": [{"name": "output", "method": "build"}],
                            },
                        },
                        "type": "genericNode",
                    },
                ],
                "edges": [
                    {
                        "source": "input-node",
                        "target": "middle-node",
                        "data": {
                            "sourceHandle": {"name": "output"},
                            "targetHandle": {"fieldName": "input_0"},
                        },
                    },
                    {
                        "source": "middle-node",
                        "target": "output-node",
                        "data": {
                            "sourceHandle": {"name": "output"},
                            "targetHandle": {"fieldName": "input_0"},
                        },
                    },
                ],
            }
        }

        workflow = converter.convert(workflow_data)

        # Check that steps are reordered based on dependencies
        step_ids = [step.id for step in workflow.steps]

        # The Prompt (middle-node) should generate steps (blob + UDF executor)
        # Step count may vary with routing improvements, focus on dependency ordering
        middle_node_steps = [sid for sid in step_ids if "middle-node" in sid]
        assert len(middle_node_steps) > 0, f"Expected middle-node steps in {step_ids}"

        # Verify no forward references
        for i, step in enumerate(workflow.steps):
            if hasattr(step, "input") and step.input:
                step_input = get_step_input_dict(step)
                for _key, value in step_input.items():
                    # Unwrap ValueExpr if needed
                    if hasattr(value, "actual_instance"):
                        value = value.actual_instance
                    if isinstance(value, dict) and "$step" in str(value):
                        from_step = value.get("$step", "")
                        if from_step:
                            # Find position of referenced step
                            try:
                                ref_pos = step_ids.index(from_step)
                                assert ref_pos < i, (
                                    f"Step {step.id} at position {i} "
                                    f"references {from_step} at position {ref_pos} "
                                    "(forward reference)"
                                )
                            except ValueError:
                                pytest.fail(f"Step {step.id} references undefined step {from_step}")

    def test_complex_dependency_ordering(self, converter: LangflowConverter):
        """Test topological sorting with complex dependencies like memory_chatbot."""
        # Simulate the memory_chatbot structure with trivial custom code
        trivial_code = """
from langflow.custom.custom_component.component import Component
from langflow.io import Output

class TrivialComponent(Component):
    outputs = [Output(display_name="Output", name="output", method="build")]

    def build(self) -> str:
        return "trivial result"
"""

        workflow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "ChatInput-1",
                        "data": {
                            "type": "TrivialChatInput",
                            "node": {
                                "template": {"code": {"value": trivial_code}},
                                "outputs": [{"name": "output", "method": "build"}],
                            },
                        },
                        "type": "genericNode",
                    },
                    {
                        "id": "ChatOutput-2",
                        "data": {
                            "type": "TrivialChatOutput",
                            "node": {
                                "template": {"code": {"value": trivial_code}},
                                "outputs": [{"name": "output", "method": "build"}],
                            },
                        },
                        "type": "genericNode",
                    },
                    {
                        "id": "Memory-3",
                        "data": {
                            "type": "TrivialMemory",
                            "node": {
                                "template": {"code": {"value": trivial_code}},
                                "outputs": [{"name": "output", "method": "build"}],
                            },
                        },
                        "type": "genericNode",
                    },
                    {
                        "id": "Prompt-4",
                        "data": {
                            "type": "TrivialPrompt",
                            "node": {
                                "template": {"code": {"value": trivial_code}},
                                "outputs": [{"name": "output", "method": "build"}],
                            },
                        },
                        "type": "genericNode",
                    },
                    {
                        "id": "LLM-5",
                        "data": {
                            "type": "TrivialLLM",
                            "node": {
                                "template": {"code": {"value": trivial_code}},
                                "outputs": [{"name": "output", "method": "build"}],
                            },
                        },
                        "type": "genericNode",
                    },
                ],
                "edges": [
                    {
                        "source": "Memory-3",
                        "target": "Prompt-4",
                        "data": {
                            "sourceHandle": {"name": "output"},
                            "targetHandle": {"fieldName": "input_0"},
                        },
                    },
                    {
                        "source": "Prompt-4",
                        "target": "LLM-5",
                        "data": {
                            "sourceHandle": {"name": "output"},
                            "targetHandle": {"fieldName": "input_0"},
                        },
                    },
                    {
                        "source": "ChatInput-1",
                        "target": "LLM-5",
                        "data": {
                            "sourceHandle": {"name": "output"},
                            "targetHandle": {"fieldName": "input_1"},
                        },
                    },
                    {
                        "source": "LLM-5",
                        "target": "ChatOutput-2",
                        "data": {
                            "sourceHandle": {"name": "output"},
                            "targetHandle": {"fieldName": "input_0"},
                        },
                    },
                ],
            }
        }

        workflow = converter.convert(workflow_data)
        step_ids = [step.id for step in workflow.steps]

        # Find the main processing steps (not blob steps)
        # Step count may vary with routing improvements, focus on dependency ordering
        memory_steps = [sid for sid in step_ids if "Memory-3" in sid and "_blob" not in sid]
        prompt_steps = [sid for sid in step_ids if "Prompt-4" in sid and "_blob" not in sid]
        llm_steps = [sid for sid in step_ids if "LLM-5" in sid and "_blob" not in sid]

        # Verify the main processing steps exist
        assert len(memory_steps) > 0, f"Expected memory processing step in {step_ids}"
        assert len(prompt_steps) > 0, f"Expected prompt processing step in {step_ids}"
        assert len(llm_steps) > 0, f"Expected llm processing step in {step_ids}"

        # Check dependency ordering between main processing steps
        memory_pos = step_ids.index(memory_steps[0])
        prompt_pos = step_ids.index(prompt_steps[0])
        llm_pos = step_ids.index(llm_steps[0])

        # Memory should come before Prompt (Memory -> Prompt)
        assert memory_pos < prompt_pos, f"Memory should come before Prompt: {step_ids}"

        # Prompt should come before LLM (Prompt -> LLM)
        assert prompt_pos < llm_pos, f"Prompt should come before LLM: {step_ids}"

    def test_component_routing_strategy_with_custom_code(self):
        """Test that components with custom code create custom blobs."""
        converter = LangflowConverter()

        # Create workflow with component that has custom code
        workflow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "custom-component",
                        "data": {
                            "type": "CustomComponent",
                            "node": {
                                "template": {
                                    "code": {
                                        "value": """
from langflow.custom.custom_component.component import Component
from langflow.io import Output

class CustomComponent(Component):
    def custom_method(self):
        return "Custom implementation"
"""
                                    },
                                    "param1": {"type": "str", "value": "test"},
                                },
                                "outputs": [{"name": "output", "method": "custom_method"}],
                                "base_classes": ["Component"],
                                "display_name": "Custom Component",
                                "metadata": {"module": "custom.module"},
                            },
                            "outputs": [{"name": "output", "method": "custom_method"}],
                        },
                    }
                ],
                "edges": [],
            }
        }

        workflow = converter.convert(workflow_data)

        # Should create blob + custom_code steps for component with custom code
        step_components = [step.component for step in workflow.steps]
        assert "/builtin/put_blob" in step_components, "Should create blob step for custom code"
        assert "/langflow/custom_code" in step_components, "Should route custom code to custom code executor"

        # Find the blob step and verify it contains the custom code
        blob_steps = [step for step in workflow.steps if step.component == "/builtin/put_blob"]
        assert len(blob_steps) > 0, "Should have at least one blob step"

        blob_step = blob_steps[0]
        blob_input = get_step_input_dict(blob_step)
        blob_data = blob_input.get("data", {})
        assert "code" in blob_data, "Blob should contain component code"
        code_value = blob_data["code"]
        # Primitives are wrapped in LiteralExpr by the flow builder
        assert hasattr(code_value, "literal"), "code should be a LiteralExpr"
        assert "CustomComponent" in code_value.literal, "Should contain custom component class"

    def test_component_routing_strategy_rejects_incomplete_components(self):
        """Test that components without custom code are rejected (unified approach)."""
        converter = LangflowConverter()

        # Create workflow with component missing custom code (invalid scenario)
        workflow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "incomplete-component",
                        "data": {
                            "type": "IncompleteComponent",
                            "node": {
                                "template": {
                                    "param1": {"type": "str", "value": "test"}
                                    # No "code" field - this is incomplete/invalid
                                },
                                "outputs": [{"name": "output", "method": "build"}],
                                "base_classes": ["Component"],
                                "display_name": "Incomplete Component",
                                "metadata": {},
                            },
                            "outputs": [{"name": "output", "method": "build"}],
                        },
                    }
                ],
                "edges": [],
            }
        }

        # Should raise ConversionError for components without custom code
        with pytest.raises(ConversionError, match="has no custom code"):
            converter.convert(workflow_data)
