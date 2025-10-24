"""
Professional Langflow Compatibility Helper for the Dynamic Agent Specification Framework.

This module provides comprehensive compatibility utilities for ensuring generated
workflows are fully compatible with Langflow UI and execution environment.
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class LangflowCompatibilityHelper:
    """
    Professional helper for ensuring Langflow compatibility.

    This helper provides:
    - Workflow structure validation for Langflow format
    - Handle encoding/decoding for Langflow edges
    - Template field optimization for frontend compatibility
    - Performance optimization for large workflows
    - Version compatibility checking
    - UI layout optimization
    """

    def __init__(self):
        """Initialize the Langflow compatibility helper."""
        self.langflow_version = "1.0.0"
        self.required_workflow_fields = self._get_required_workflow_fields()
        self.required_node_fields = self._get_required_node_fields()
        self.required_edge_fields = self._get_required_edge_fields()
        self.performance_thresholds = self._get_performance_thresholds()

    def optimize_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize workflow for Langflow compatibility and performance.

        Args:
            workflow: Workflow dictionary to optimize

        Returns:
            Optimized workflow dictionary
        """
        try:
            logger.debug("Starting Langflow workflow optimization")

            # Create a copy to avoid modifying the original
            optimized = self._deep_copy_dict(workflow)

            # Phase 1: Structure optimization
            optimized = self._optimize_workflow_structure(optimized)

            # Phase 2: Node optimization
            optimized = self._optimize_nodes(optimized)

            # Phase 3: Edge optimization
            optimized = self._optimize_edges(optimized)

            # Phase 4: UI layout optimization
            optimized = self._optimize_ui_layout(optimized)

            # Phase 5: Performance optimization
            optimized = self._optimize_performance(optimized)

            logger.debug("Successfully optimized workflow for Langflow compatibility")
            return optimized

        except Exception as e:
            logger.error(f"Failed to optimize workflow: {e}")
            return workflow  # Return original if optimization fails

    def validate_workflow_structure(self, workflow: Dict[str, Any]) -> List[str]:
        """
        Validate workflow structure for Langflow compatibility.

        Args:
            workflow: Workflow dictionary to validate

        Returns:
            List of validation error messages
        """
        errors = []

        try:
            # Validate top-level structure
            for field in self.required_workflow_fields:
                if field not in workflow:
                    errors.append(f"Missing required workflow field: {field}")

            # Validate data structure
            data = workflow.get("data", {})
            if not isinstance(data, dict):
                errors.append("Workflow 'data' field must be a dictionary")
                return errors

            # Validate nodes and edges
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])

            if not isinstance(nodes, list):
                errors.append("Workflow nodes must be a list")

            if not isinstance(edges, list):
                errors.append("Workflow edges must be a list")

            # Validate individual nodes
            node_errors = self._validate_nodes_structure(nodes)
            errors.extend(node_errors)

            # Validate individual edges
            edge_errors = self._validate_edges_structure(edges)
            errors.extend(edge_errors)

            # Validate node-edge relationships
            relationship_errors = self._validate_node_edge_relationships(nodes, edges)
            errors.extend(relationship_errors)

        except Exception as e:
            errors.append(f"Structure validation failed: {str(e)}")

        return errors

    def calculate_compatibility_score(self, workflow: Dict[str, Any]) -> float:
        """
        Calculate compatibility score for workflow (0.0 to 1.0).

        Args:
            workflow: Workflow dictionary to score

        Returns:
            Compatibility score between 0.0 and 1.0
        """
        try:
            score = 1.0
            penalties = []

            # Check structure compliance
            structure_errors = self.validate_workflow_structure(workflow)
            if structure_errors:
                penalty = min(0.3, len(structure_errors) * 0.05)
                score -= penalty
                penalties.append(f"Structure issues: -{penalty:.2f}")

            # Check node compatibility
            nodes = workflow.get("data", {}).get("nodes", [])
            node_score, node_penalty = self._calculate_node_compatibility_score(nodes)
            score -= node_penalty
            if node_penalty > 0:
                penalties.append(f"Node issues: -{node_penalty:.2f}")

            # Check edge compatibility
            edges = workflow.get("data", {}).get("edges", [])
            edge_score, edge_penalty = self._calculate_edge_compatibility_score(edges)
            score -= edge_penalty
            if edge_penalty > 0:
                penalties.append(f"Edge issues: -{edge_penalty:.2f}")

            # Check performance characteristics
            perf_penalty = self._calculate_performance_penalty(workflow)
            score -= perf_penalty
            if perf_penalty > 0:
                penalties.append(f"Performance issues: -{perf_penalty:.2f}")

            # Ensure score is within bounds
            score = max(0.0, min(1.0, score))

            if penalties:
                logger.debug(f"Compatibility score: {score:.2f}, penalties: {', '.join(penalties)}")

            return score

        except Exception as e:
            logger.warning(f"Failed to calculate compatibility score: {e}")
            return 0.5  # Return moderate score if calculation fails

    def encode_edge_handle(self, handle_data: Dict[str, Any]) -> str:
        """
        Encode edge handle data for Langflow format.

        Args:
            handle_data: Handle data dictionary

        Returns:
            Encoded handle string with œ delimiters
        """
        try:
            # Convert to JSON and replace quotes with œ for Langflow compatibility
            json_str = json.dumps(handle_data)
            encoded = json_str.replace('"', 'œ')
            return encoded

        except Exception as e:
            logger.warning(f"Failed to encode edge handle: {e}")
            return json.dumps(handle_data)  # Fallback to regular JSON

    def decode_edge_handle(self, encoded_handle: str) -> Dict[str, Any]:
        """
        Decode edge handle data from Langflow format.

        Args:
            encoded_handle: Encoded handle string

        Returns:
            Decoded handle data dictionary
        """
        try:
            # Replace œ delimiters with quotes and parse JSON
            json_str = encoded_handle.replace('œ', '"')
            return json.loads(json_str)

        except Exception as e:
            logger.warning(f"Failed to decode edge handle: {e}")
            return {}  # Return empty dict if decoding fails

    def optimize_template_for_frontend(self,
                                     template: Dict[str, Any],
                                     component_type: str) -> Dict[str, Any]:
        """
        Optimize node template for Langflow frontend compatibility.

        Args:
            template: Node template dictionary
            component_type: Langflow component type

        Returns:
            Optimized template dictionary
        """
        try:
            optimized = self._deep_copy_dict(template)

            # Ensure all template fields have required frontend properties
            for field_name, field_config in optimized.items():
                if isinstance(field_config, dict):
                    optimized[field_name] = self._optimize_template_field(field_config, field_name)

            # Add component-specific optimizations
            optimized = self._add_component_specific_optimizations(optimized, component_type)

            return optimized

        except Exception as e:
            logger.warning(f"Failed to optimize template for frontend: {e}")
            return template

    def generate_optimal_layout(self,
                              nodes: List[Dict[str, Any]],
                              edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate optimal layout positions for nodes.

        Args:
            nodes: List of workflow nodes
            edges: List of workflow edges

        Returns:
            Nodes with optimized positions
        """
        try:
            if not nodes:
                return nodes

            logger.debug(f"Generating optimal layout for {len(nodes)} nodes")

            # Create copy of nodes
            positioned_nodes = [self._deep_copy_dict(node) for node in nodes]

            # Build adjacency graph for layout calculation
            graph = self._build_layout_graph(positioned_nodes, edges)

            # Calculate optimal positions using force-directed layout
            positions = self._calculate_force_directed_layout(graph, positioned_nodes)

            # Apply positions to nodes
            for i, node in enumerate(positioned_nodes):
                if i < len(positions):
                    node["position"] = {"x": positions[i][0], "y": positions[i][1]}

            logger.debug("Successfully generated optimal layout")
            return positioned_nodes

        except Exception as e:
            logger.warning(f"Failed to generate optimal layout: {e}")
            return nodes

    def _optimize_workflow_structure(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize top-level workflow structure."""
        # Ensure required fields exist
        if "data" not in workflow:
            workflow["data"] = {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}

        data = workflow["data"]
        if "nodes" not in data:
            data["nodes"] = []
        if "edges" not in data:
            data["edges"] = []
        if "viewport" not in data:
            data["viewport"] = {"x": 0, "y": 0, "zoom": 1}

        # Ensure metadata exists
        if "metadata" not in workflow:
            workflow["metadata"] = {}

        # Add Langflow-specific metadata
        workflow["metadata"].update({
            "langflow_version": self.langflow_version,
            "optimized_at": datetime.utcnow().isoformat(),
            "optimization_version": "2.0.0"
        })

        # Ensure tags list exists
        if "tags" not in workflow:
            workflow["tags"] = []

        # Add framework tag if not present
        if "specification_framework" not in workflow["tags"]:
            workflow["tags"].append("specification_framework")

        return workflow

    def _optimize_nodes(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize workflow nodes for Langflow compatibility."""
        nodes = workflow.get("data", {}).get("nodes", [])

        for node in nodes:
            # Ensure required node fields
            if "type" not in node:
                node["type"] = "genericNode"
            if "position" not in node:
                node["position"] = {"x": 0, "y": 0}
            if "data" not in node:
                node["data"] = {}
            if "selected" not in node:
                node["selected"] = False
            if "width" not in node:
                node["width"] = 384
            if "height" not in node:
                node["height"] = 256

            # Optimize node data
            node_data = node["data"]

            # Ensure display_name exists
            if "display_name" not in node_data and "type" in node_data:
                node_data["display_name"] = node_data["type"]

            # Optimize template
            if "template" in node_data:
                component_type = node_data.get("type", "")
                node_data["template"] = self.optimize_template_for_frontend(
                    node_data["template"], component_type
                )

            # Ensure node.template exists (for nested access)
            if "node" not in node_data:
                node_data["node"] = {}
            if "template" not in node_data["node"]:
                node_data["node"]["template"] = node_data.get("template", {})

        return workflow

    def _optimize_edges(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize workflow edges for Langflow compatibility."""
        edges = workflow.get("data", {}).get("edges", [])

        for edge in edges:
            # Ensure required edge fields
            if "type" not in edge:
                edge["type"] = "default"
            if "animated" not in edge:
                edge["animated"] = False
            if "style" not in edge:
                edge["style"] = {}
            if "data" not in edge:
                edge["data"] = {}

            # Optimize edge data
            edge_data = edge["data"]

            # Ensure targetHandle and sourceHandle are in data
            if "targetHandle" not in edge_data and "targetHandle" in edge:
                edge_data["targetHandle"] = edge["targetHandle"]
            if "sourceHandle" not in edge_data and "sourceHandle" in edge:
                edge_data["sourceHandle"] = edge["sourceHandle"]

            # Encode handles if they are objects
            if "targetHandle" in edge and isinstance(edge["targetHandle"], dict):
                edge["targetHandle"] = self.encode_edge_handle(edge["targetHandle"])
            if "sourceHandle" in edge and isinstance(edge["sourceHandle"], dict):
                edge["sourceHandle"] = self.encode_edge_handle(edge["sourceHandle"])

        return workflow

    def _optimize_ui_layout(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize UI layout and positioning."""
        data = workflow.get("data", {})
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        # Generate optimal layout if nodes lack proper positioning
        needs_layout = any(
            node.get("position", {}).get("x", 0) == 0 and node.get("position", {}).get("y", 0) == 0
            for node in nodes
        )

        if needs_layout and len(nodes) > 1:
            try:
                optimized_nodes = self.generate_optimal_layout(nodes, edges)
                data["nodes"] = optimized_nodes
            except Exception as e:
                logger.warning(f"Failed to generate optimal layout: {e}")

        # Optimize viewport
        if nodes:
            # Calculate bounding box
            positions = [node.get("position", {}) for node in nodes]
            x_coords = [pos.get("x", 0) for pos in positions]
            y_coords = [pos.get("y", 0) for pos in positions]

            if x_coords and y_coords:
                min_x, max_x = min(x_coords), max(x_coords)
                min_y, max_y = min(y_coords), max(y_coords)

                # Center viewport on content
                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2

                data["viewport"] = {
                    "x": -center_x + 400,  # Offset for UI panels
                    "y": -center_y + 200,
                    "zoom": 1
                }

        return workflow

    def _optimize_performance(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize workflow for performance."""
        # Remove unnecessary metadata for large workflows
        node_count = len(workflow.get("data", {}).get("nodes", []))

        if node_count > self.performance_thresholds["large_workflow_node_count"]:
            # Simplify templates for large workflows
            self._simplify_templates_for_performance(workflow)

            # Add performance warning to metadata
            if "metadata" not in workflow:
                workflow["metadata"] = {}

            workflow["metadata"]["performance_optimized"] = True
            workflow["metadata"]["large_workflow"] = True

        return workflow

    def _optimize_template_field(self, field_config: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Optimize a single template field for frontend compatibility."""
        optimized = field_config.copy()

        # Ensure required frontend fields
        if "show" not in optimized:
            optimized["show"] = True

        if "input_types" not in optimized:
            optimized["input_types"] = ["Message", "Data"]

        if "name" not in optimized:
            optimized["name"] = field_name

        if "required" not in optimized:
            optimized["required"] = False

        if "advanced" not in optimized:
            optimized["advanced"] = field_name.startswith("_")

        if "placeholder" not in optimized:
            optimized["placeholder"] = f"Enter {field_name.replace('_', ' ')}"

        if "password" not in optimized:
            optimized["password"] = field_name.lower() in ["password", "api_key", "secret", "token"]

        # Optimize field type
        if "type" not in optimized and "value" in optimized:
            optimized["type"] = self._infer_field_type(optimized["value"])

        # Optimize multiline setting
        if "multiline" not in optimized:
            if isinstance(optimized.get("value"), str):
                optimized["multiline"] = len(str(optimized["value"])) > 100
            else:
                optimized["multiline"] = False

        return optimized

    def _add_component_specific_optimizations(self,
                                            template: Dict[str, Any],
                                            component_type: str) -> Dict[str, Any]:
        """Add component-specific template optimizations."""
        if component_type == "ChatOpenAI":
            # Ensure OpenAI-specific fields have proper configurations
            openai_optimizations = {
                "model_name": {"options": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]},
                "temperature": {"min": 0.0, "max": 2.0, "step": 0.1},
                "max_tokens": {"min": 1, "max": 4000, "step": 1}
            }

            for field_name, optimization in openai_optimizations.items():
                if field_name in template:
                    template[field_name].update(optimization)

        elif component_type == "PromptTemplate":
            # Ensure PromptTemplate-specific optimizations
            if "template" in template:
                template["template"]["multiline"] = True
                template["template"]["rows"] = 4

        return template

    def _validate_nodes_structure(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Validate nodes structure."""
        errors = []

        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                errors.append(f"Node {i} must be a dictionary")
                continue

            for field in self.required_node_fields:
                if field not in node:
                    errors.append(f"Node {i} missing required field: {field}")

            # Validate position
            if "position" in node:
                position = node["position"]
                if not isinstance(position, dict) or "x" not in position or "y" not in position:
                    errors.append(f"Node {i} position must be dict with x, y coordinates")

        return errors

    def _validate_edges_structure(self, edges: List[Dict[str, Any]]) -> List[str]:
        """Validate edges structure."""
        errors = []

        for i, edge in enumerate(edges):
            if not isinstance(edge, dict):
                errors.append(f"Edge {i} must be a dictionary")
                continue

            for field in self.required_edge_fields:
                if field not in edge:
                    errors.append(f"Edge {i} missing required field: {field}")

        return errors

    def _validate_node_edge_relationships(self,
                                        nodes: List[Dict[str, Any]],
                                        edges: List[Dict[str, Any]]) -> List[str]:
        """Validate relationships between nodes and edges."""
        errors = []

        # Build set of valid node IDs
        node_ids = {node.get("id") for node in nodes if node.get("id")}

        # Validate edge references
        for i, edge in enumerate(edges):
            source = edge.get("source")
            target = edge.get("target")

            if source and source not in node_ids:
                errors.append(f"Edge {i} references non-existent source node: {source}")

            if target and target not in node_ids:
                errors.append(f"Edge {i} references non-existent target node: {target}")

        return errors

    def _calculate_node_compatibility_score(self, nodes: List[Dict[str, Any]]) -> Tuple[float, float]:
        """Calculate node compatibility score and penalty."""
        if not nodes:
            return 1.0, 0.0

        total_score = 0.0
        for node in nodes:
            node_score = 1.0

            # Check required fields
            for field in self.required_node_fields:
                if field not in node:
                    node_score -= 0.2

            # Check template completeness
            template = node.get("data", {}).get("template", {})
            if template:
                template_score = self._calculate_template_score(template)
                node_score *= template_score

            total_score += node_score

        avg_score = total_score / len(nodes)
        penalty = max(0.0, 1.0 - avg_score)

        return avg_score, penalty

    def _calculate_edge_compatibility_score(self, edges: List[Dict[str, Any]]) -> Tuple[float, float]:
        """Calculate edge compatibility score and penalty."""
        if not edges:
            return 1.0, 0.0

        total_score = 0.0
        for edge in edges:
            edge_score = 1.0

            # Check required fields
            for field in self.required_edge_fields:
                if field not in edge:
                    edge_score -= 0.2

            # Check handle encoding
            target_handle = edge.get("targetHandle", "")
            if isinstance(target_handle, str) and "œ" in target_handle:
                try:
                    self.decode_edge_handle(target_handle)
                except Exception:
                    edge_score -= 0.1

            total_score += edge_score

        avg_score = total_score / len(edges)
        penalty = max(0.0, 1.0 - avg_score)

        return avg_score, penalty

    def _calculate_performance_penalty(self, workflow: Dict[str, Any]) -> float:
        """Calculate performance penalty based on workflow characteristics."""
        penalty = 0.0

        node_count = len(workflow.get("data", {}).get("nodes", []))
        edge_count = len(workflow.get("data", {}).get("edges", []))

        # Node count penalty
        if node_count > self.performance_thresholds["warning_node_count"]:
            penalty += 0.1
        if node_count > self.performance_thresholds["large_workflow_node_count"]:
            penalty += 0.2

        # Edge count penalty
        if edge_count > self.performance_thresholds["warning_edge_count"]:
            penalty += 0.1

        return min(penalty, 0.5)  # Cap at 0.5

    def _calculate_template_score(self, template: Dict[str, Any]) -> float:
        """Calculate template completeness score."""
        if not template:
            return 1.0

        required_frontend_fields = ["show", "input_types", "name"]
        total_fields = len(template)
        complete_fields = 0

        for field_config in template.values():
            if isinstance(field_config, dict):
                has_required = all(rf in field_config for rf in required_frontend_fields)
                if has_required:
                    complete_fields += 1

        return complete_fields / total_fields if total_fields > 0 else 1.0

    def _simplify_templates_for_performance(self, workflow: Dict[str, Any]) -> None:
        """Simplify templates for large workflows to improve performance."""
        nodes = workflow.get("data", {}).get("nodes", [])

        for node in nodes:
            template = node.get("data", {}).get("template", {})
            if len(template) > 10:  # Simplify complex templates
                # Keep only essential fields
                essential_fields = ["_type", "model_name", "temperature", "template", "input_value"]
                simplified = {k: v for k, v in template.items() if k in essential_fields}
                node["data"]["template"] = simplified

    def _build_layout_graph(self,
                          nodes: List[Dict[str, Any]],
                          edges: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Build adjacency graph for layout calculation."""
        graph = {node["id"]: [] for node in nodes}

        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target and source in graph:
                graph[source].append(target)

        return graph

    def _calculate_force_directed_layout(self,
                                       graph: Dict[str, List[str]],
                                       nodes: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
        """Calculate force-directed layout positions."""
        import math
        import random

        if len(nodes) <= 1:
            return [(200, 200)]

        # Initialize random positions
        positions = {}
        for node in nodes:
            positions[node["id"]] = (
                random.uniform(100, 800),
                random.uniform(100, 600)
            )

        # Force-directed layout simulation
        iterations = 50
        for _ in range(iterations):
            forces = {node_id: (0, 0) for node_id in positions}

            # Repulsive forces between all nodes
            node_ids = list(positions.keys())
            for i, node1 in enumerate(node_ids):
                for node2 in node_ids[i+1:]:
                    x1, y1 = positions[node1]
                    x2, y2 = positions[node2]

                    dx = x2 - x1
                    dy = y2 - y1
                    distance = math.sqrt(dx*dx + dy*dy) + 0.1

                    # Repulsive force
                    force = 1000 / (distance * distance)
                    fx = -force * dx / distance
                    fy = -force * dy / distance

                    forces[node1] = (forces[node1][0] + fx, forces[node1][1] + fy)
                    forces[node2] = (forces[node2][0] - fx, forces[node2][1] - fy)

            # Attractive forces between connected nodes
            for source, targets in graph.items():
                for target in targets:
                    if source in positions and target in positions:
                        x1, y1 = positions[source]
                        x2, y2 = positions[target]

                        dx = x2 - x1
                        dy = y2 - y1
                        distance = math.sqrt(dx*dx + dy*dy) + 0.1

                        # Attractive force
                        force = distance * 0.01
                        fx = force * dx / distance
                        fy = force * dy / distance

                        forces[source] = (forces[source][0] + fx, forces[source][1] + fy)
                        forces[target] = (forces[target][0] - fx, forces[target][1] - fy)

            # Apply forces with damping
            damping = 0.9
            for node_id in positions:
                x, y = positions[node_id]
                fx, fy = forces[node_id]

                x += fx * damping
                y += fy * damping

                # Keep within bounds
                x = max(100, min(800, x))
                y = max(100, min(600, y))

                positions[node_id] = (x, y)

        # Return positions in node order
        return [positions[node["id"]] for node in nodes]

    def _infer_field_type(self, value: Any) -> str:
        """Infer field type from value."""
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, list):
            return "list"
        elif isinstance(value, dict):
            return "dict"
        else:
            return "str"

    def _deep_copy_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deep copy of a dictionary."""
        try:
            return json.loads(json.dumps(data))
        except (TypeError, ValueError):
            # Fallback for non-serializable objects
            return {key: self._manual_deep_copy(value) for key, value in data.items()}

    def _manual_deep_copy(self, data: Any) -> Any:
        """Manual deep copy implementation."""
        if isinstance(data, dict):
            return {key: self._manual_deep_copy(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._manual_deep_copy(item) for item in data]
        else:
            return data

    def _get_required_workflow_fields(self) -> List[str]:
        """Get required fields for Langflow workflows."""
        return ["data", "name", "description"]

    def _get_required_node_fields(self) -> List[str]:
        """Get required fields for Langflow nodes."""
        return ["id", "data", "position", "type"]

    def _get_required_edge_fields(self) -> List[str]:
        """Get required fields for Langflow edges."""
        return ["id", "source", "target"]

    def _get_performance_thresholds(self) -> Dict[str, int]:
        """Get performance thresholds for optimization."""
        return {
            "warning_node_count": 30,
            "large_workflow_node_count": 50,
            "warning_edge_count": 80,
            "max_template_fields": 15
        }