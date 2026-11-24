"""Unit tests for LangflowConverter."""

from typing import Any

import pytest

from langflow_stepflow.exceptions import ConversionError
from langflow_stepflow.translation.translator import LangflowConverter


def get_step_input_dict(step) -> dict:
    """Extract the input dict from a step.

    With the msgspec-based SDK, step.input is already a plain dict.
    """
    if step.input is None:
        return {}
    if isinstance(step.input, dict):
        return step.input
    import msgspec

    return msgspec.to_builtins(step.input)


def find_step(workflow, step_id):
    """Return the step with the given id, or None."""
    return next((s for s in workflow.steps if s.id == step_id), None)


def ref_step_id(value) -> str | None:
    """Return the step id a serialized step reference points to, or None.

    A Stepflow step reference serializes to ``{"$step": <step_id>, "path": ...}``.
    """
    if isinstance(value, dict):
        return value.get("$step")
    return None


def flow_output(workflow) -> Any:
    """Return the workflow's output as a plain (msgspec-decoded) value."""
    if workflow.output is None:
        return None
    import msgspec

    return msgspec.to_builtins(workflow.output)


# A known core component (hash/module taken from known_components.KNOWN_COMPONENTS).
# Conversion only checks the hash/module tables, so any matching pair routes the
# node through the core executor without importing the module.
_KNOWN_CODE_HASH = "bb5f8714781b"  # pragma: allowlist secret
_KNOWN_MODULE = "lfx.components.models.language_model.LanguageModelComponent"


# Minimal custom-component code; only its truthiness matters to the translator,
# which routes any component carrying code to the custom_code executor.
_COMPONENT_CODE = """
from langflow.custom.custom_component.component import Component
from langflow.io import Output

class TrivialComponent(Component):
    outputs = [Output(display_name="Output", name="output", method="build")]

    def build(self) -> str:
        return "trivial result"
"""


def _custom_node(node_id: str, component_type: str, outputs: list[dict[str, str]]) -> dict[str, Any]:
    """Build a custom-code Langflow node with the given outputs."""
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {
            "type": component_type,
            "node": {
                "template": {"code": {"value": _COMPONENT_CODE}},
                "outputs": outputs,
            },
        },
    }


def _edge(source: str, target: str, source_output: str, target_field: str) -> dict[str, Any]:
    """Build a Langflow edge carrying explicit source-output and target-field handles."""
    return {
        "source": source,
        "target": target,
        "data": {
            "sourceHandle": {"name": source_output},
            "targetHandle": {"fieldName": target_field},
        },
    }


def _multi_output_fanout_workflow() -> dict[str, Any]:
    """A single source whose two distinct outputs each feed a different consumer."""
    return {
        "data": {
            "nodes": [
                _custom_node(
                    "splitter",
                    "Splitter",
                    [
                        {"name": "output_a", "method": "build_a"},
                        {"name": "output_b", "method": "build_b"},
                    ],
                ),
                _custom_node("consumer-a", "ConsumerA", [{"name": "output", "method": "build"}]),
                _custom_node("consumer-b", "ConsumerB", [{"name": "output", "method": "build"}]),
            ],
            "edges": [
                _edge("splitter", "consumer-a", "output_a", "input_0"),
                _edge("splitter", "consumer-b", "output_b", "input_0"),
            ],
        }
    }


def _single_output_fanout_workflow() -> dict[str, Any]:
    """A single source whose one output feeds two different consumers."""
    return {
        "data": {
            "nodes": [
                _custom_node("source", "Source", [{"name": "output", "method": "build"}]),
                _custom_node("consumer-a", "ConsumerA", [{"name": "output", "method": "build"}]),
                _custom_node("consumer-b", "ConsumerB", [{"name": "output", "method": "build"}]),
            ],
            "edges": [
                _edge("source", "consumer-a", "output", "input_0"),
                _edge("source", "consumer-b", "output", "input_0"),
            ],
        }
    }


def _known_core_node(node_id: str, component_type: str, outputs: list[dict[str, str]]) -> dict[str, Any]:
    """Build a Langflow node that routes through the core executor (no blob)."""
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {
            "type": component_type,
            "node": {
                "template": {"param": {"type": "str", "value": "x"}},
                "outputs": outputs,
                "metadata": {"code_hash": _KNOWN_CODE_HASH, "module": _KNOWN_MODULE},
            },
        },
    }


def _multi_output_fanout_core_workflow() -> dict[str, Any]:
    """Multi-output fan-out where the source routes through the core executor."""
    return {
        "data": {
            "nodes": [
                _known_core_node(
                    "splitter-core",
                    "Splitter",
                    [
                        {"name": "output_a", "method": "build_a"},
                        {"name": "output_b", "method": "build_b"},
                    ],
                ),
                _known_core_node("consumer-a", "ConsumerA", [{"name": "output", "method": "build"}]),
                _known_core_node("consumer-b", "ConsumerB", [{"name": "output", "method": "build"}]),
            ],
            "edges": [
                _edge("splitter-core", "consumer-a", "output_a", "input_0"),
                _edge("splitter-core", "consumer-b", "output_b", "input_0"),
            ],
        }
    }


def _fanout_to_chat_output_workflow() -> dict[str, Any]:
    """A source whose *non-primary* output feeds ChatOutput (the workflow output).

    The first edge (to a plain consumer) makes ``output_a`` primary, so ChatOutput,
    wired to ``output_b``, must resolve to the secondary step.
    """
    return {
        "data": {
            "nodes": [
                _custom_node(
                    "splitter",
                    "Splitter",
                    [
                        {"name": "output_a", "method": "build_a"},
                        {"name": "output_b", "method": "build_b"},
                    ],
                ),
                _custom_node("consumer", "Consumer", [{"name": "output", "method": "build"}]),
                {
                    "id": "ChatOutput-1",
                    "type": "genericNode",
                    "data": {
                        "type": "ChatOutput",
                        "node": {
                            "template": {},
                            "outputs": [{"name": "message", "method": "message_response"}],
                        },
                    },
                },
            ],
            "edges": [
                _edge("splitter", "consumer", "output_a", "input_0"),
                _edge("splitter", "ChatOutput-1", "output_b", "input_value"),
            ],
        }
    }


class TestLangflowConverter:
    """Test LangflowConverter functionality."""

    def test_init_default(self):
        """Test default initialization."""
        converter = LangflowConverter()
        assert converter is not None

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
        # Code may be a plain string or a $literal wrapper depending on SDK version
        if isinstance(code_value, dict):
            assert "CustomComponent" in str(code_value), "Should contain custom component class"
        else:
            assert "CustomComponent" in code_value, "Should contain custom component class"

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

    def test_build_output_mapping_is_edge_scoped(self, converter: LangflowConverter):
        """Output mapping is keyed per (source, target), not collapsed per source.

        Regression guard for issue #12308: a node fanning out different outputs
        must retain a distinct output per outgoing connection.
        """
        edges = [
            {"source": "x", "target": "t1", "data": {"sourceHandle": {"name": "out_a"}}},
            {"source": "x", "target": "t2", "data": {"sourceHandle": {"name": "out_b"}}},
        ]

        mapping = converter._build_output_mapping_from_edges(edges)

        assert mapping == {("x", "t1"): "out_a", ("x", "t2"): "out_b"}

    def test_build_source_outputs_collects_distinct_outputs(self, converter: LangflowConverter):
        """Distinct outputs per source are collected in first-seen edge order."""
        mapping = {
            ("x", "t1"): "out_a",
            ("x", "t2"): "out_b",
            ("x", "t3"): "out_a",  # repeat of out_a to a third target
            ("y", "t4"): "only",
        }

        source_outputs = converter._build_source_outputs(mapping)

        assert source_outputs == {"x": ["out_a", "out_b"], "y": ["only"]}

    def test_multi_output_fanout_routes_each_branch_to_its_own_output(self, converter: LangflowConverter):
        """Multi-output fan-out wires each consumer to the correct output (issue #12308).

        Before the fix, a single source step was created with a "first-edge-wins"
        selected output, so every consumer received the same (wrong) output.
        """
        workflow = converter.convert(_multi_output_fanout_workflow())
        step_ids = {step.id for step in workflow.steps}

        # The source materializes one executor step per distinct fanned-out output.
        assert "langflow_splitter" in step_ids
        assert "langflow_splitter__output_b" in step_ids

        # Each materialized source step selects the output its branch needs.
        primary_blob = get_step_input_dict(find_step(workflow, "langflow_splitter_blob"))
        secondary_blob = get_step_input_dict(find_step(workflow, "langflow_splitter__output_b_blob"))
        assert primary_blob["data"]["selected_output"] == "output_a"
        assert secondary_blob["data"]["selected_output"] == "output_b"

        # The crux: each consumer references the step matching its edge's output,
        # and the two consumers reference *different* steps.
        consumer_a_inputs = get_step_input_dict(find_step(workflow, "langflow_consumer-a"))["input"]
        consumer_b_inputs = get_step_input_dict(find_step(workflow, "langflow_consumer-b"))["input"]
        a_ref = ref_step_id(consumer_a_inputs["input_0"])
        b_ref = ref_step_id(consumer_b_inputs["input_0"])

        assert a_ref == "langflow_splitter"
        assert b_ref == "langflow_splitter__output_b"
        assert a_ref != b_ref

    def test_single_output_fanout_reuses_one_source_step(self, converter: LangflowConverter):
        """A node fanning out the *same* output to many targets stays a single step.

        Guards against over-materialization: per-output steps are only created when
        the outputs actually differ.
        """
        workflow = converter.convert(_single_output_fanout_workflow())
        step_ids = [step.id for step in workflow.steps]

        # Only one executor step for the source (no per-output duplication).
        source_executor_steps = [
            sid for sid in step_ids if sid == "langflow_source" or sid.startswith("langflow_source__")
        ]
        assert source_executor_steps == ["langflow_source"]

        # Both consumers reference that single source step.
        for consumer in ("langflow_consumer-a", "langflow_consumer-b"):
            consumer_inputs = get_step_input_dict(find_step(workflow, consumer))["input"]
            assert ref_step_id(consumer_inputs["input_0"]) == "langflow_source"

    def test_multi_output_fanout_core_executor_path(self, converter: LangflowConverter):
        """Fan-out routing also works for the core-executor path (no blob steps).

        The core path embeds ``selected_output`` directly in the step input rather
        than in a blob, so it needs its own coverage.
        """
        workflow = converter.convert(_multi_output_fanout_core_workflow())
        step_ids = {step.id for step in workflow.steps}

        assert "langflow_splitter-core" in step_ids
        assert "langflow_splitter-core__output_b" in step_ids

        # Each core step carries the correct selected_output inline.
        primary = get_step_input_dict(find_step(workflow, "langflow_splitter-core"))
        secondary = get_step_input_dict(find_step(workflow, "langflow_splitter-core__output_b"))
        assert primary["selected_output"] == "output_a"
        assert secondary["selected_output"] == "output_b"

        # Each consumer is wired to the step matching its edge's output.
        a_ref = ref_step_id(get_step_input_dict(find_step(workflow, "langflow_consumer-a"))["input"]["input_0"])
        b_ref = ref_step_id(get_step_input_dict(find_step(workflow, "langflow_consumer-b"))["input"]["input_0"])
        assert a_ref == "langflow_splitter-core"
        assert b_ref == "langflow_splitter-core__output_b"

    def test_chat_output_resolves_non_primary_fanout_output(self, converter: LangflowConverter):
        """ChatOutput wired to a source's non-primary output gets that output.

        Regression guard: the ChatOutput / workflow-output paths previously used the
        source's primary ref, so connecting ChatOutput to a secondary output silently
        returned the wrong result.
        """
        workflow = converter.convert(_fanout_to_chat_output_workflow())

        # The plain consumer takes the primary output (output_a)...
        consumer_inputs = get_step_input_dict(find_step(workflow, "langflow_consumer"))["input"]
        assert ref_step_id(consumer_inputs["input_0"]) == "langflow_splitter"

        # ...and the workflow output (driven by ChatOutput) takes output_b.
        assert ref_step_id(flow_output(workflow)) == "langflow_splitter__output_b"
