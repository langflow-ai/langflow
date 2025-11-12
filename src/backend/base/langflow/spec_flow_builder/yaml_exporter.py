"""Flow to YAML Exporter - Converts existing flows to YAML specifications."""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class FlowToYamlConverter:
    """
    Converts existing flow JSON to YAML specification format.

    This class is responsible for:
    - Extracting flow metadata (name, description, version)
    - Converting nodes to YAML components
    - Analyzing edges to build provides relationships
    - Resolving component types from node data
    - Extracting user-configured values
    """

    def __init__(self, all_components: Dict[str, Any]):
        """
        Initialize the FlowToYamlConverter.

        Args:
            all_components: Component catalog from get_and_cache_all_types_dict()
                           Structure: {category: {component_name: component_data}}
        """
        self.all_components = all_components
        logger.info("FlowToYamlConverter initialized")

    def _extract_metadata(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract flow metadata for YAML header.

        Args:
            flow_data: Complete flow data including name, description, etc.

        Returns:
            Dictionary with metadata fields (id, name, description, version, status)
        """
        metadata = {
            "id": flow_data.get("id", ""),
            "name": flow_data.get("name", "Unnamed Flow"),
            "description": flow_data.get("description", ""),
            "version": "1.0.0",  # Default version
            "status": "ACTIVE",
        }

        logger.debug(f"Extracted metadata: {metadata['name']} (id: {metadata['id']})")
        return metadata

    def _resolve_component_type(self, node: Dict[str, Any]) -> Optional[str]:
        """
        Resolve the component type (class name) from node data.

        This maps the display name or component info back to the actual class name
        (e.g., "Prompt" -> "PromptComponent", "Chat Input" -> "ChatInput").

        Args:
            node: Node dictionary with data.node structure

        Returns:
            Component class name (e.g., "PromptComponent") or None if not found
        """
        try:
            node_data = node.get("data", {})
            node_template = node_data.get("node", {})

            # Try to get from template.code.value (contains class definition)
            if "template" in node_template and "code" in node_template["template"]:
                code_value = node_template["template"]["code"].get("value", "")
                # Extract class name from code (e.g., "class PromptComponent")
                for line in code_value.split("\n"):
                    if line.strip().startswith("class ") and "(" in line:
                        class_name = line.strip().split("class ")[1].split("(")[0].strip()
                        logger.debug(f"Resolved component type from code: {class_name}")
                        return class_name

            # Fallback: Try to match display_name with catalog
            display_name = node_template.get("display_name", "")
            if display_name:
                # Search in catalog for matching display_name
                for category, components in self.all_components.items():
                    for component_name, component_data in components.items():
                        if component_data.get("display_name") == display_name:
                            # Extract class name from component code
                            if "template" in component_data and "code" in component_data["template"]:
                                code = component_data["template"]["code"].get("value", "")
                                for line in code.split("\n"):
                                    if line.strip().startswith("class ") and "(" in line:
                                        class_name = line.strip().split("class ")[1].split("(")[0].strip()
                                        logger.debug(
                                            f"Resolved component type for '{display_name}': {class_name}"
                                        )
                                        return class_name

            logger.warning(f"Could not resolve component type for node {node.get('id')}")
            return None

        except Exception as e:
            logger.error(f"Error resolving component type for node {node.get('id')}: {e}", exc_info=True)
            return None

    def _get_catalog_template(self, component_type: str) -> Dict[str, Any]:
        """
        Get the default template for a component from the catalog.

        This looks up the component in self.all_components (from /api/v1/all)
        and returns its template with default field values.

        Reuses the same search pattern as _resolve_component_type().

        Args:
            component_type: Component class name (e.g., "AgentComponent")

        Returns:
            Template dict with default field values, or {} if not found
        """
        if not component_type:
            return {}

        # Reuse same search pattern as _resolve_component_type() (lines 87-99)
        for category, components in self.all_components.items():
            for component_name, component_data in components.items():
                # Try to match by extracting class name from code
                if "template" in component_data and "code" in component_data["template"]:
                    code = component_data["template"]["code"].get("value", "")
                    for line in code.split("\n"):
                        if line.strip().startswith("class ") and "(" in line:
                            class_name = line.strip().split("class ")[1].split("(")[0].strip()
                            # If class name matches, return the template
                            if class_name == component_type:
                                logger.debug(f"Found catalog template for {component_type}")
                                return component_data.get("template", {})

        logger.warning(f"Could not find catalog template for {component_type}")
        return {}

    def _extract_node_config(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract user-configured values from node template.

        Uses a two-step approach:
        1. Check for user_configured/configured_from_spec flags (YAML-created flows)
        2. Compare against catalog defaults (imported JSON flows)

        Only exports fields that:
        - Have user_configured or configured_from_spec flags, OR
        - Have values different from catalog defaults

        Skips:
        - System/internal fields (code, _type, display_name, etc.)
        - Auto-generated fields (tools_metadata, add_current_date_tool)
        - Fields with values matching catalog defaults

        Args:
            node: Node dictionary with template

        Returns:
            Dictionary of config key-value pairs (only user-configured)
        """
        # System/internal fields to always skip
        SKIP_FIELDS = {
            "code",  # Component source code
            "_type",  # Internal type marker
            "display_name",  # Component display name
            "name",  # Component name
            # "template" removed - it's a valid config field for PromptComponent
            "description",  # Component description
        }

        # Auto-generated fields that should not be exported
        AUTO_GENERATED_FIELDS = {
            "tools_metadata",  # Auto-generated tool metadata
            "add_current_date_tool",  # Auto-added current date tool
        }

        config = {}

        # Get component type to look up catalog defaults
        component_type = self._resolve_component_type(node)

        # Get catalog template for default values
        catalog_template = self._get_catalog_template(component_type)

        node_template = node.get("data", {}).get("node", {}).get("template", {})

        for field_name, field_data in node_template.items():
            if not isinstance(field_data, dict):
                continue

            # Skip system fields
            if field_name in SKIP_FIELDS or field_name.startswith("_"):
                continue

            # Skip auto-generated fields
            if field_name in AUTO_GENERATED_FIELDS:
                logger.debug(f"Skipping auto-generated field: {field_name}")
                continue

            # Get flow value
            flow_value = field_data.get("value")

            # Skip only truly undefined values (allow empty strings through for comparison)
            if flow_value == "__UNDEFINED__":
                continue

            # STEP 1: Check flags first (for YAML-created flows)
            is_user_configured = field_data.get("user_configured", False)
            is_spec_configured = field_data.get("configured_from_spec", False)

            if is_user_configured or is_spec_configured:
                config[field_name] = flow_value
                logger.debug(f"Exported {field_name} (has user_configured/spec flag)")
                continue

            # STEP 2: Compare against catalog default (for imported JSON flows)
            # Get the default value from catalog
            catalog_field = catalog_template.get(field_name, {})

            # If field doesn't exist in catalog, it's dynamically created
            if not catalog_field:
                # Export dynamic fields only if non-empty
                if flow_value not in (None, ""):
                    config[field_name] = flow_value
                    logger.debug(f"Exported {field_name}: {repr(flow_value)[:50]} (dynamic field, non-empty)")
                else:
                    logger.debug(f"Skipped {field_name}: dynamic field with empty value")
                continue

            catalog_default = catalog_field.get("value") if isinstance(catalog_field, dict) else None

            # If value differs from default, user changed it
            if flow_value != catalog_default:
                config[field_name] = flow_value
                logger.debug(f"Exported {field_name}: {repr(flow_value)[:50]} (default: {repr(catalog_default)[:50]})")
            else:
                logger.debug(f"Skipped {field_name}: matches default ({repr(catalog_default)[:50]})")

        return config

    def _build_edge_map(self, edges: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Build a map of source node -> list of target connections.

        Handles two edge formats:
        1. New format: edge.data.targetHandle.fieldName (most common)
        2. Old format: edge.targetHandle = "id|field|type" (fallback)

        Args:
            edges: List of edge objects from flow

        Returns:
            Dictionary mapping source node ID to list of {target_id, target_input, output_types, input_types} dicts
        """
        edge_map = defaultdict(list)

        logger.info(f"Building edge map from {len(edges)} edges")

        for idx, edge in enumerate(edges):
            source = edge.get("source")
            target = edge.get("target")

            logger.debug(f"Processing edge {idx}: source={source}, target={target}")

            # ===== FORMAT 1: Try NEW format first (edge.data.targetHandle.fieldName) =====
            # This is the format from imported JSON flows
            edge_data = edge.get("data", {})
            if edge_data and isinstance(edge_data, dict):
                target_handle_data = edge_data.get("targetHandle", {})
                source_handle_data = edge_data.get("sourceHandle", {})
                if isinstance(target_handle_data, dict):
                    field_name = target_handle_data.get("fieldName")
                    if field_name:
                        # Extract type information for tool identification
                        output_types = source_handle_data.get("output_types", []) if isinstance(source_handle_data, dict) else []
                        input_types = target_handle_data.get("inputTypes", [])

                        edge_map[source].append({
                            "target_id": target,
                            "target_input": field_name,
                            "output_types": output_types,
                            "input_types": input_types
                        })
                        logger.debug(f"✓ Mapped edge (new format): {source} -> {target}.{field_name} (output_types={output_types}, input_types={input_types})")
                        continue  # Successfully processed, move to next edge

            # ===== FORMAT 2: Try OLD format (targetHandle = "id|field|type") =====
            # Fallback for older flow formats or YAML-created flows
            target_handle = edge.get("targetHandle", "")
            if isinstance(target_handle, str) and "|" in target_handle:
                parts = target_handle.split("|")
                if len(parts) >= 2:
                    field_name = parts[1]
                    edge_map[source].append({
                        "target_id": target,
                        "target_input": field_name,
                        "output_types": [],
                        "input_types": []
                    })
                    logger.debug(f"✓ Mapped edge (old format): {source} -> {target}.{field_name}")
                    continue  # Successfully processed, move to next edge

            # ===== If we reach here, couldn't parse edge =====
            logger.warning(
                f"Could not parse edge {idx}: source={source}, target={target}, "
                f"edge_data={bool(edge_data)}, targetHandle type={type(edge.get('targetHandle'))}"
            )

        logger.info(f"Built edge map with {len(edge_map)} source nodes having outgoing connections")
        for source_id, connections in edge_map.items():
            logger.debug(f"  {source_id} -> {len(connections)} connections")

        return edge_map

    def _nodes_to_components(
        self, nodes: List[Dict[str, Any]], edge_map: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Convert flow nodes to YAML components with provides relationships.

        Args:
            nodes: List of node dictionaries from flow
            edge_map: Mapping of source node -> target connections

        Returns:
            List of YAML component dictionaries
        """
        components = []

        # First, build a mapping of node_id -> yaml_component_id
        # This is needed to convert edge references back to YAML component IDs
        node_to_yaml_id = {}
        for node in nodes:
            node_id = node.get("id")
            yaml_comp_id = node.get("data", {}).get("yaml_component_id")

            # If yaml_component_id exists, use it; otherwise use node_id
            if yaml_comp_id:
                node_to_yaml_id[node_id] = yaml_comp_id
            else:
                # For manually created flows, use node_id as component ID
                node_to_yaml_id[node_id] = node_id

        for node in nodes:
            node_id = node.get("id")
            node_data = node.get("data", {})
            node_template = node_data.get("node", {})

            # Use yaml_component_id if available, otherwise use node_id
            component_id = node_to_yaml_id.get(node_id, node_id)

            # Extract basic component info
            component = {
                "id": component_id,
                "name": node_template.get("display_name", "Component"),
                "type": self._resolve_component_type(node),
                "description": node_template.get("description", ""),
            }

            # Extract config (only user-configured values)
            config = self._extract_node_config(node)
            if config:
                component["config"] = config

            # Check if component was used as a tool
            # Method 1: Check tool_mode flag (existing flows)
            tool_mode = node_template.get("tool_mode", False)

            # Method 2: Check if any edge from this node has output_types containing "Tool"
            has_tool_output = False
            if node_id in edge_map:
                for connection in edge_map[node_id]:
                    if "Tool" in connection.get("output_types", []):
                        has_tool_output = True
                        break

            if tool_mode or has_tool_output:
                component["asTools"] = True

            # Build provides relationships from edges
            if node_id in edge_map:
                provides = []
                for connection in edge_map[node_id]:
                    # Map target node_id to yaml_component_id
                    target_node_id = connection["target_id"]
                    target_yaml_id = node_to_yaml_id.get(target_node_id, target_node_id)

                    # Determine useAs value
                    # If input_types contains "Tool", use "tools" as the useAs value
                    use_as = connection["target_input"]
                    if "Tool" in connection.get("input_types", []):
                        use_as = "tools"

                    provides.append(
                        {
                            "useAs": use_as,
                            "in": target_yaml_id,
                            "description": f"Provides {use_as} to {target_yaml_id}",
                        }
                    )
                component["provides"] = provides

            components.append(component)
            logger.debug(f"Converted node to component: {component['id']} ({component['name']})")

        return components

    def _generate_yaml_string(self, spec: Dict[str, Any]) -> str:
        """
        Generate formatted YAML string from specification dictionary.

        Args:
            spec: Complete specification dictionary

        Returns:
            Formatted YAML string
        """
        # Custom YAML dumper configuration
        yaml_str = yaml.dump(
            spec,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
            indent=2,
        )

        logger.debug(f"Generated YAML string ({len(yaml_str)} chars)")
        return yaml_str

    async def convert_flow_to_yaml(self, flow_data: Dict[str, Any]) -> str:
        """
        Convert complete flow to YAML specification.

        This is the main method that orchestrates the conversion:
        1. Extracts metadata from flow
        2. Builds edge map for provides relationships
        3. Converts nodes to components
        4. Generates formatted YAML string

        Args:
            flow_data: Complete flow data including nodes, edges, metadata

        Returns:
            YAML specification string

        Raises:
            ValueError: If flow data is invalid or conversion fails
        """
        logger.info(f"Converting flow to YAML: {flow_data.get('name', 'unknown')}")

        try:
            # Extract flow structure
            flow_json = flow_data.get("data", {})
            if isinstance(flow_json, str):
                import json

                flow_json = json.loads(flow_json)

            nodes = flow_json.get("nodes", [])
            edges = flow_json.get("edges", [])

            if not nodes:
                logger.warning("No nodes found in flow")
                raise ValueError("Flow has no nodes to convert")

            logger.info(f"Converting {len(nodes)} nodes and {len(edges)} edges")

            # Build specification structure
            spec = {}

            # 1. Add metadata
            metadata = self._extract_metadata(flow_data)
            spec.update(metadata)

            # 2. Build edge map for provides relationships
            edge_map = self._build_edge_map(edges)

            # 3. Convert nodes to components
            components = self._nodes_to_components(nodes, edge_map)
            spec["components"] = components

            # 4. Generate YAML string
            yaml_string = self._generate_yaml_string(spec)

            logger.info(f"Successfully converted flow to YAML ({len(components)} components)")
            return yaml_string

        except Exception as e:
            logger.error(f"Error converting flow to YAML: {e}", exc_info=True)
            raise ValueError(f"Failed to convert flow to YAML: {str(e)}")
