"""Edge Builder - Connects flow nodes based on component relationships."""

import json
import logging
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class EdgeBuilder:
    """
    Builds edges (connections) between flow nodes.

    This class is responsible for:
    - Parsing 'provides' relationships from YAML
    - Creating edges between nodes
    - Mapping output/input connections
    """

    def __init__(self, all_components: Dict[str, Any]):
        """
        Initialize the EdgeBuilder.

        Args:
            all_components: Component catalog from get_and_cache_all_types_dict()
                           Structure: {category: {component_name: component_data}}
        """
        self.all_components = all_components
        logger.info("EdgeBuilder initialized")

    def _find_node_by_yaml_id(self, nodes: List[Dict[str, Any]], yaml_component_id: str) -> Optional[Dict[str, Any]]:
        """
        Find node by yaml_component_id.

        Args:
            nodes: List of node dictionaries
            yaml_component_id: The YAML component ID to search for

        Returns:
            Matching node dictionary or None if not found
        """
        for node in nodes:
            if node.get("data", {}).get("yaml_component_id") == yaml_component_id:
                return node
        return None

    def _encode_handle_string(self, handle_dict: Dict[str, Any]) -> str:
        """
        Encode handle dictionary as JSON string with \\u0153 (œ) instead of quotes.

        Args:
            handle_dict: Dictionary to encode

        Returns:
            JSON string with quotes replaced by \\u0153
        """
        # Convert dict to JSON string
        json_string = json.dumps(handle_dict, separators=(",", ":"), ensure_ascii=False)

        # Replace double quotes with \u0153
        encoded_string = json_string.replace('"', "\u0153")

        return encoded_string

    def _build_source_handle(self, source_node: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        """
        Build sourceHandle structure from source node.

        For tool components (asTools: true), uses the tool-specific output structure.
        For regular components, uses the component's first output.

        Args:
            source_node: The source node dictionary

        Returns:
            Tuple of (handle_dict, encoded_handle_string)
        """
        node_data = source_node.get("data", {}).get("node", {})
        node_id = source_node.get("id")
        # Get the component type from data.type (e.g., "Prompt Template", "KnowledgeHubSearch")
        data_type = source_node.get("data", {}).get("type", node_data.get("display_name", ""))

        # Check if this is a tool component
        is_tool = source_node.get("data", {}).get("asTools", False)

        if is_tool:
            # Tool components always use these fixed values
            output_name = "component_as_tool"
            output_types = ["Tool"]
            logger.debug(f"Building source handle for tool component {node_id}: name={output_name}, types={output_types}")
        else:
            # Regular components - get from outputs[0]
            outputs = node_data.get("outputs", [])
            if not outputs:
                logger.warning(f"Node {node_id} has no outputs, using defaults")
                output_name = "output"
                output_types = ["Message"]
            else:
                first_output = outputs[0]
                output_name = first_output.get("name", "output")
                output_types = first_output.get("types", ["Message"])

        # Build handle dict
        handle_dict = {"dataType": data_type, "id": node_id, "name": output_name, "output_types": output_types}

        # Encode with \u0153
        encoded_string = self._encode_handle_string(handle_dict)

        return handle_dict, encoded_string

    def _build_target_handle(
        self, target_node: Dict[str, Any], use_as: str
    ) -> tuple[Dict[str, Any], str]:
        """
        Build targetHandle structure from target node and useAs field.

        Args:
            target_node: The target node dictionary
            use_as: The 'useAs' field name from provides relationship

        Returns:
            Tuple of (handle_dict, encoded_handle_string)
        """
        node_data = target_node.get("data", {}).get("node", {})
        node_id = target_node.get("id")

        # Get template field for the useAs parameter
        template = node_data.get("template", {})
        field = template.get(use_as, {})

        # Extract field metadata
        field_name = use_as
        field_type = field.get("type", "str")
        input_types = field.get("input_types", ["Message"])

        # Build handle dict
        handle_dict = {"fieldName": field_name, "id": node_id, "inputTypes": input_types, "type": field_type}

        # Encode with \u0153
        encoded_string = self._encode_handle_string(handle_dict)

        return handle_dict, encoded_string

    def _generate_edge_id(self, source_id: str, source_handle: str, target_id: str, target_handle: str) -> str:
        """
        Generate edge ID in the format: xy-edge__{source}{sourceHandle}-{target}{targetHandle}.

        Args:
            source_id: Source node ID
            source_handle: Encoded source handle string
            target_id: Target node ID
            target_handle: Encoded target handle string

        Returns:
            Edge ID string
        """
        edge_id = f"xy-edge__{source_id}{source_handle}-{target_id}{target_handle}"
        return edge_id

    def _build_single_edge(
        self, source_node: Dict[str, Any], target_node: Dict[str, Any], use_as: str
    ) -> Dict[str, Any]:
        """
        Build a single edge structure.

        Args:
            source_node: Source node dictionary
            target_node: Target node dictionary
            use_as: The 'useAs' field name from provides relationship

        Returns:
            Complete edge structure
        """
        # Build source and target handles
        source_handle_dict, source_handle_encoded = self._build_source_handle(source_node)
        target_handle_dict, target_handle_encoded = self._build_target_handle(target_node, use_as)

        # Get node IDs
        source_id = source_node.get("id")
        target_id = target_node.get("id")

        # Generate edge ID
        edge_id = self._generate_edge_id(source_id, source_handle_encoded, target_id, target_handle_encoded)

        # Build complete edge structure
        edge = {
            "source": source_id,
            "sourceHandle": source_handle_encoded,
            "target": target_id,
            "targetHandle": target_handle_encoded,
            "data": {"targetHandle": target_handle_dict, "sourceHandle": source_handle_dict},
            "id": edge_id,
        }

        logger.debug(f"Built edge: {source_id} -> {target_id} (useAs: {use_as})")
        return edge

    async def build_edges(self, nodes: List[Dict[str, Any]], yaml_content: str) -> List[Dict[str, Any]]:
        """
        Build edges from YAML specification 'provides' relationships.

        This method:
        1. Parses YAML to find all components with 'provides' sections
        2. For each provides entry:
           - Finds source node (the component with provides)
           - Finds target node (the component named in provides.in)
           - Builds sourceHandle from source node outputs
           - Builds targetHandle from target node template field (provides.useAs)
           - Encodes handles with \\u0153 instead of quotes
           - Creates edge with proper ID format

        Args:
            nodes: List of node dictionaries
            yaml_content: YAML specification content

        Returns:
            List of edge dictionaries connecting the nodes

        Raises:
            ValueError: If edge relationships are invalid
        """
        logger.info(f"Building edges for {len(nodes)} nodes")

        # Debug: Log all node yaml_component_ids
        node_yaml_ids = [node.get("data", {}).get("yaml_component_id") for node in nodes]
        logger.info(f"Available node yaml_component_ids: {node_yaml_ids}")

        try:
            # Parse YAML to get components
            spec = yaml.safe_load(yaml_content)
            yaml_components = spec.get("components", [])

            if not yaml_components:
                logger.warning("No components found in YAML specification")
                return []

            logger.info(f"Found {len(yaml_components)} components in YAML")

            edges = []

            # Process each component looking for 'provides' relationships
            for yaml_component in yaml_components:
                component_id = yaml_component.get("id")
                provides_list = yaml_component.get("provides", [])

                logger.debug(f"Processing component {component_id}: provides={provides_list}")

                if not provides_list:
                    logger.debug(f"Component {component_id} has no provides relationships")
                    continue

                # Find source node for this component
                source_node = self._find_node_by_yaml_id(nodes, component_id)
                if not source_node:
                    logger.warning(f"Could not find source node for component {component_id}")
                    logger.warning(f"Searched for yaml_component_id='{component_id}' in nodes with ids: {node_yaml_ids}")
                    continue

                logger.info(f"Found source node {source_node.get('id')} for component {component_id}")
                logger.info(f"Processing {len(provides_list)} provides entries for component {component_id}")

                # Process each provides entry
                for provides_entry in provides_list:
                    use_as = provides_entry.get("useAs")
                    target_yaml_id = provides_entry.get("in")
                    description = provides_entry.get("description", "")

                    logger.debug(f"Provides entry: useAs={use_as}, in={target_yaml_id}, description={description}")

                    if not use_as or not target_yaml_id:
                        logger.warning(
                            f"Invalid provides entry in component {component_id}: missing 'useAs' or 'in'"
                        )
                        continue

                    # Find target node
                    target_node = self._find_node_by_yaml_id(nodes, target_yaml_id)
                    if not target_node:
                        logger.warning(
                            f"Could not find target node for component {target_yaml_id} "
                            f"(referenced by {component_id})"
                        )
                        logger.warning(f"Searched for yaml_component_id='{target_yaml_id}' in nodes with ids: {node_yaml_ids}")
                        continue

                    logger.info(f"Found target node {target_node.get('id')} for component {target_yaml_id}")

                    # Build edge
                    try:
                        edge = self._build_single_edge(source_node, target_node, use_as)
                        edges.append(edge)

                        logger.info(
                            f"✓ Created edge: {source_node.get('id')} -> {target_node.get('id')} "
                            f"(useAs: {use_as}, description: {description})"
                        )
                    except Exception as e:
                        logger.error(f"Failed to build edge from {component_id} to {target_yaml_id}: {e}", exc_info=True)
                        continue

            logger.info(f"✓ Successfully created {len(edges)} edges total")

            return edges

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML: {e}")
            raise ValueError(f"Invalid YAML format: {str(e)}")
        except Exception as e:
            logger.error(f"Error building edges: {e}", exc_info=True)
            raise ValueError(f"Failed to build edges: {str(e)}")
