"""Main Langflow to Stepflow converter implementation."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from stepflow_py.worker import Flow, FlowBuilder, Value

from ..exceptions import ConversionError
from .dependency_analyzer import DependencyAnalyzer
from .node_processor import NodeProcessor
from .schema_mapper import SchemaMapper


@dataclass
class WorkflowAnalysis:
    """Typed analysis results from analyzing a Langflow workflow."""

    node_count: int  # Total number of nodes in the Langflow workflow
    edge_count: int  # Total number of connections/edges between nodes
    # Map of component type names to their counts (e.g., {"ChatInput": 1, "OpenAI": 2})
    component_types: dict[str, int]
    dependencies: dict[
        str, list[str]
    ]  # Map of node IDs to lists of their dependency node IDs
    potential_issues: list[
        str
    ]  # List of warnings or potential problems detected during analysis


class LangflowConverter:
    """Convert Langflow JSON workflows to Stepflow YAML workflows."""

    def __init__(self):
        """Initialize the converter."""
        self.dependency_analyzer = DependencyAnalyzer()
        self.schema_mapper = SchemaMapper()
        self.node_processor = NodeProcessor()

    def convert_file(self, input_path: str | Path) -> str:
        """Convert a Langflow JSON file to Stepflow YAML.

        Args:
            input_path: Path to the Langflow JSON file

        Returns:
            Stepflow YAML as a string

        Raises:
            ConversionError: If conversion fails
            ValidationError: If validation fails
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise ConversionError(f"Input file not found: {input_path}")

        try:
            with open(input_path, encoding="utf-8") as f:
                langflow_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConversionError(f"Invalid JSON in {input_path}: {e}") from e
        except Exception as e:
            raise ConversionError(f"Error reading {input_path}: {e}") from e

        workflow = self.convert(langflow_data)
        return self.to_yaml(workflow)

    def convert(self, langflow_data: dict[str, Any]) -> Flow:
        """Convert Langflow data structure to Stepflow workflow.

        Args:
            langflow_data: Parsed Langflow JSON data

        Returns:
            Flow object

        Raises:
            ConversionError: If conversion fails
        """
        self.node_processor.reset()
        try:
            # Extract main data structure
            if "data" not in langflow_data:
                raise ConversionError("Invalid Langflow JSON: missing 'data' key")

            data = langflow_data["data"]
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])

            if not nodes:
                raise ConversionError("No nodes found in Langflow workflow")

            # Build dependency graph from edges
            dependencies = self.dependency_analyzer.build_dependency_graph(edges)

            # Get proper execution order using topological sort
            execution_order = self.dependency_analyzer.get_execution_order(dependencies)

            # Create field mapping from edges for proper UDF input handling
            field_mapping = self._build_field_mapping_from_edges(edges)

            # Create output mapping from edges to track which output is used from
            # each component
            output_mapping = self._build_output_mapping_from_edges(edges)

            # Create node lookup for efficient processing
            node_lookup = {node["id"]: node for node in nodes}

            # Create FlowBuilder
            builder = FlowBuilder(name=self._generate_workflow_name(langflow_data))

            # Note: Skip setting input schema for now as Schema class doesn't
            # support properties
            # input_schema = self._generate_input_section(nodes)
            # if input_schema:
            #     builder.set_input_schema(input_schema)

            # Process nodes and collect output references
            node_output_refs: dict[str, Any] = {}  # node_id -> output reference
            processed_nodes = set()

            # First, process nodes in execution order
            for node_id in execution_order:
                if node_id in node_lookup:
                    output_ref = self.node_processor.process_node(
                        node_lookup[node_id],
                        dependencies,
                        builder,
                        node_output_refs,
                        field_mapping,
                        output_mapping,
                    )
                    if output_ref is not None:
                        node_output_refs[node_id] = output_ref
                    processed_nodes.add(node_id)

            # Then, process any remaining nodes (nodes with no dependencies)
            for node in nodes:
                node_id = node["id"]
                if node_id not in processed_nodes:
                    output_ref = self.node_processor.process_node(
                        node,
                        dependencies,
                        builder,
                        node_output_refs,
                        field_mapping,
                        output_mapping,
                    )
                    if output_ref is not None:
                        node_output_refs[node_id] = output_ref

            # Set workflow output using incremental output building
            self._build_flow_output(builder, nodes, dependencies, node_output_refs)

            # Set variable schema
            if self.node_processor.variables:
                builder.set_variables_schema(
                    {"type": "object", "properties": self.node_processor.variables}
                )

            # Build and return the flow
            flow = builder.build()
            return flow

        except ConversionError:
            raise
        except Exception as e:
            raise ConversionError(f"Unexpected error during conversion: {e}") from e

    def to_yaml(self, workflow: Flow) -> str:
        """Convert Flow to YAML string.

        Args:
            workflow: Flow object (Pydantic model from stepflow_py.api.models)

        Returns:
            YAML string
        """
        try:
            # Convert Flow to dict using Pydantic's model_dump
            # Use by_alias=True to get the JSON field names (camelCase)
            # Use exclude_unset=True to remove unset values
            workflow_dict = workflow.model_dump(by_alias=True, exclude_unset=True)

            # Generate clean YAML
            return yaml.dump(
                workflow_dict,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=120,
            )
        except Exception as e:
            raise ConversionError(f"Error generating YAML: {e}") from e

    def analyze(self, langflow_data: dict[str, Any]) -> WorkflowAnalysis:
        """Analyze Langflow workflow structure without conversion.

        Args:
            langflow_data: Parsed Langflow JSON data

        Returns:
            Typed analysis results
        """
        try:
            data = langflow_data.get("data", {})
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])

            # Basic statistics
            analysis: dict[str, Any] = {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "component_types": {},
                "dependencies": {},
                "potential_issues": [],
            }

            # Analyze nodes
            for node in nodes:
                node_data = node.get("data", {})
                component_type = node_data.get("type", "Unknown")

                if component_type not in analysis["component_types"]:
                    analysis["component_types"][component_type] = 0
                analysis["component_types"][component_type] += 1

                # Check for potential issues
                if not node.get("id"):
                    analysis["potential_issues"].append("Node missing ID")
                if not node_data.get("node", {}).get("template"):
                    analysis["potential_issues"].append(
                        f"Node {node.get('id', 'unknown')} missing template"
                    )

            # Analyze dependencies
            dependencies = self.dependency_analyzer.build_dependency_graph(edges)

            return WorkflowAnalysis(
                node_count=len(nodes),
                edge_count=len(edges),
                component_types=analysis["component_types"],
                dependencies=dependencies,
                potential_issues=analysis["potential_issues"],
            )

        except Exception as e:
            raise ConversionError(f"Error analyzing workflow: {e}") from e

    def _generate_workflow_name(self, langflow_data: dict[str, Any]) -> str:
        """Generate a workflow name from Langflow data."""
        # Try to get name from various sources
        if "name" in langflow_data:
            name = langflow_data["name"]
            return str(name) if name is not None else "Converted Langflow Workflow"

        data = langflow_data.get("data", {})
        if "name" in data:
            name = data["name"]
            return str(name) if name is not None else "Converted Langflow Workflow"

        # Fallback to generic name
        return "Converted Langflow Workflow"

    def _build_field_mapping_from_edges(
        self, edges: list[dict[str, Any]]
    ) -> dict[str, dict[str, str]]:
        """Build field mapping from edges for proper input handling.

        Args:
            edges: List of Langflow edges

        Returns:
            Dict mapping target_node_id -> {source_node_id -> target_field_name}
        """
        field_mapping: dict[str, dict[str, str]] = {}

        for edge in edges:
            target_id = edge.get("target")
            source_id = edge.get("source")

            if not target_id or not source_id:
                continue

            # Get target field name from edge data
            edge_data = edge.get("data", {})
            target_handle = edge_data.get("targetHandle", {})

            if isinstance(target_handle, dict):
                field_name = target_handle.get("fieldName")
            elif isinstance(target_handle, str):
                # Sometimes targetHandle is a JSON string - handle this case
                try:
                    import json

                    target_info = json.loads(target_handle.replace("œ", '"'))
                    field_name = target_info.get("fieldName")
                except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
                    field_name = None
            else:
                field_name = None

            if field_name:
                if target_id not in field_mapping:
                    field_mapping[target_id] = {}
                field_mapping[target_id][source_id] = field_name

        return field_mapping

    def _build_output_mapping_from_edges(
        self, edges: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Build output mapping from edges to track output usage per component.

        Args:
            edges: List of Langflow edges

        Returns:
            Dict mapping source_node_id -> output_name
        """
        output_mapping: dict[str, str] = {}

        for edge in edges:
            source_id = edge.get("source")

            if not source_id:
                continue

            # Get source output name from edge data
            edge_data = edge.get("data", {})
            source_handle = edge_data.get("sourceHandle", {})

            output_name = None
            if isinstance(source_handle, dict):
                output_name = source_handle.get("name")
            elif isinstance(source_handle, str):
                # Sometimes sourceHandle is a JSON string - handle this case
                try:
                    import json

                    source_info = json.loads(source_handle.replace("œ", '"'))
                    output_name = source_info.get("name")
                except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
                    output_name = None

            # Only store if we found an output name and don't have one already
            # (first edge wins if component has multiple outgoing edges with
            # different outputs)
            if output_name and source_id not in output_mapping:
                output_mapping[source_id] = output_name

        return output_mapping

    def _build_flow_output(
        self,
        builder: FlowBuilder,
        nodes: list[dict[str, Any]],
        dependencies: dict[str, list[str]],
        node_output_refs: dict[str, Any],
    ) -> None:
        """Build workflow output using incremental output building API.

        Args:
            builder: FlowBuilder instance to add output fields to
            nodes: Original Langflow nodes
            dependencies: Dependency graph
            node_output_refs: Mapping of node IDs to their output references
        """
        # Look for ChatOutput nodes first
        chat_output_nodes = [
            n for n in nodes if n.get("data", {}).get("type") == "ChatOutput"
        ]

        if chat_output_nodes:
            # Use the first ChatOutput node
            chat_output_node = chat_output_nodes[0]
            node_id = chat_output_node["id"]

            # Check if ChatOutput has dependencies
            if node_id in dependencies and dependencies[node_id]:
                # ChatOutput depends on another node - use that node's output
                dep_node_id = dependencies[node_id][0]
                if dep_node_id in node_output_refs:
                    builder.set_output(node_output_refs[dep_node_id])
                    return

            # ChatOutput has no dependencies or dependencies not found - check if
            # it's a simple passthrough
            if chat_output_nodes and len(nodes) <= 2:
                # Simple ChatInput -> ChatOutput workflow
                chat_input_nodes = [
                    n for n in nodes if n.get("data", {}).get("type") == "ChatInput"
                ]
                if chat_input_nodes:
                    builder.set_output(Value.input.add_path("message"))
                    return

        # Find leaf nodes (nodes with no dependents)
        dependent_nodes = set()
        for deps in dependencies.values():
            dependent_nodes.update(deps)

        leaf_nodes = []
        for node in nodes:
            node_id = node["id"]
            component_type = node.get("data", {}).get("type", "")

            # Skip ChatInput/ChatOutput as they're handled specially
            if component_type in ["ChatInput", "ChatOutput"]:
                continue

            if node_id not in dependent_nodes and node_id in node_output_refs:
                leaf_nodes.append((node_id, component_type))

        # Build structured output based on leaf nodes
        if len(leaf_nodes) == 1:
            # Single leaf node - use it directly
            node_id, _ = leaf_nodes[0]
            builder.set_output(node_output_refs[node_id])
        elif len(leaf_nodes) > 1:
            # Multiple leaf nodes - create structured output using incremental building
            for node_id, component_type in leaf_nodes:
                # Generate a clean field name from the component type
                field_name = (
                    component_type.lower().replace("component", "").replace("_", "")
                )
                if not field_name:
                    field_name = node_id.lower().replace("-", "_")

                builder.add_output_field(field_name, node_output_refs[node_id])
        else:
            # No leaf nodes found - fallback to direct input passthrough
            builder.set_output(Value.input.add_path("message"))
