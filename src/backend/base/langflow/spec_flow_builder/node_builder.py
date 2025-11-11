"""Node Builder - Creates flow nodes from YAML components."""

import logging
import secrets
from typing import Any, Dict, List, Tuple

import yaml

logger = logging.getLogger(__name__)


class NodeBuilder:
    """
    Builds flow nodes from YAML specification components.

    This class is responsible for:
    - Matching YAML component types with catalog components
    - Creating node structures with proper IDs and positions
    - Generating node IDs and positions
    """

    def __init__(self, all_components: Dict[str, Any]):
        """
        Initialize the NodeBuilder.

        Args:
            all_components: Component catalog from get_and_cache_all_types_dict()
                           Structure: {category: {component_name: component_data}}
        """
        self.all_components = all_components
        total_count = sum(len(comps) for comps in all_components.values())
        logger.info(f"NodeBuilder initialized with {total_count} components")

    def _find_component_by_type(self, yaml_type: str) -> Tuple[str, str, Dict[str, Any]]:
        """
        Find component template by searching for the class name in the code.

        Args:
            yaml_type: The component type from YAML (e.g., "PromptComponent")

        Returns:
            Tuple of (category, component_name, component_data)

        Raises:
            ValueError: If component type is not found in catalog
        """
        logger.debug(f"Looking for component with type: {yaml_type}")

        components = self.all_components
        search_pattern = f"class {yaml_type}"

        # Search through all categories and components
        for category, category_components in components.items():
            for component_name, component_data in category_components.items():
                # Check if template.code.value contains the class definition
                if "template" in component_data and "code" in component_data["template"]:
                    code_value = component_data["template"]["code"].get("value", "")
                    if search_pattern in code_value:
                        logger.info(f"Found component: {component_name} in category: {category}")
                        return category, component_name, component_data

        # Component not found
        error_msg = f"Component type '{yaml_type}' not found in catalog. Searched for: {search_pattern}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    def _generate_node_id(self, display_name: str) -> str:
        """
        Generate unique node ID in the format: {display_name}-{random}.

        Args:
            display_name: The display name of the component

        Returns:
            Unique node ID (e.g., "Prompt Template-a3f2b1")
        """
        # Generate 5-character random suffix
        random_suffix = secrets.token_hex(3)[:5]  # 6 hex chars -> take 5
        node_id = f"{display_name}-{random_suffix}"
        logger.debug(f"Generated node ID: {node_id}")
        return node_id

    def _calculate_position(self, index: int) -> Dict[str, float]:
        """
        Calculate node position for auto-layout.

        Uses a simple vertical stacking layout with some horizontal offset.

        Args:
            index: The index of the node (0-based)

        Returns:
            Position dictionary with x and y coordinates
        """
        # Start position
        start_x = 220.0
        start_y = 166.0

        # Spacing between nodes
        vertical_spacing = 300.0

        position = {"x": start_x, "y": start_y + (index * vertical_spacing)}

        logger.debug(f"Calculated position for node {index}: {position}")
        return position

    def _build_single_node(
        self, yaml_component: Dict[str, Any], index: int, component_template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build a single node structure from YAML component and component template.

        Args:
            yaml_component: Component definition from YAML
            index: Index of the component (for position calculation)
            component_template: Full component template from /api/v1/all

        Returns:
            Complete node structure ready for flow JSON
        """
        # Generate node ID
        template_display_name = component_template.get("display_name", "Component")
        node_id = self._generate_node_id(template_display_name)

        # Calculate position
        position = self._calculate_position(index)

        # Create a deep copy of the component template for the node
        import copy

        node_template = copy.deepcopy(component_template)

        # Override display_name and description from YAML
        node_template["display_name"] = yaml_component.get("name", template_display_name)
        node_template["description"] = yaml_component.get("description", node_template.get("description", ""))

        # Check if component should be used as a tool
        as_tools = yaml_component.get("asTools", False)
        if as_tools:
            node_template["tool_mode"] = True
            # Replace outputs with tool output structure
            logger.debug(f"Component {yaml_component.get('id')} has asTools=true, replacing outputs with tool structure")
            node_template["outputs"] = [
                {
                    "types": ["Tool"],
                    "selected": "Tool",
                    "name": "component_as_tool",
                    "display_name": "Toolset",
                    "method": "to_toolkit",
                    "value": "__UNDEFINED__",
                    "cache": True,
                    "required_inputs": None,
                    "allows_loop": False,
                    "group_outputs": False,
                    "options": None,
                    "tool_mode": True,
                }
            ]

        # Build the complete node structure
        node = {
            "id": node_id,
            "type": "genericNode",
            "position": position,
            "data": {
                "node": node_template,
                "showNode": True,
                "type": template_display_name,  # Original template display name
                "id": node_id,
                "yaml_component_id": yaml_component.get("id"),  # Store YAML component ID for config matching
                # "asTools": as_tools,  # Store asTools flag for EdgeBuilder
            },
            "selected": True,
            "measured": {"width": 320, "height": 254},
            "dragging": False,
        }

        logger.debug(
            f"Built node: {node_id} (type: {template_display_name}, yaml_id: {yaml_component.get('id')}, asTools: {as_tools})"
        )
        return node

    async def build_nodes(self, yaml_content: str) -> List[Dict[str, Any]]:
        """
        Build all nodes from YAML specification.

        This is the main method that:
        1. Parses the YAML content
        2. Fetches all components from /api/v1/all
        3. For each YAML component, finds the matching template
        4. Builds the node structure with proper overrides

        Args:
            yaml_content: YAML specification content

        Returns:
            List of node dictionaries ready for flow creation

        Raises:
            ValueError: If YAML is invalid, components are missing, or API calls fail
        """
        logger.info("Building nodes from YAML specification")

        try:
            # Step 1: Parse YAML
            spec = yaml.safe_load(yaml_content)
            yaml_components = spec.get("components", [])

            if not yaml_components:
                logger.warning("No components found in YAML specification")
                return []

            logger.info(f"Found {len(yaml_components)} components in YAML")

            # Step 2: Build nodes for each YAML component
            nodes = []
            for index, yaml_component in enumerate(yaml_components):
                try:
                    # Get component type from YAML
                    yaml_type = yaml_component.get("type")
                    if not yaml_type:
                        logger.warning(f"Component at index {index} has no 'type' field, skipping")
                        continue

                    yaml_id = yaml_component.get("id", f"component-{index}")
                    logger.info(f"Processing component {index + 1}/{len(yaml_components)}: {yaml_id} (type: {yaml_type})")

                    # Find matching component template
                    category, component_name, component_template = self._find_component_by_type(yaml_type)

                    # Build node structure
                    node = self._build_single_node(yaml_component, index, component_template)

                    nodes.append(node)

                except ValueError as e:
                    # Component not found or other validation error
                    logger.error(f"Failed to build node for component {yaml_component.get('id', index)}: {e}")
                    raise
                except Exception as e:
                    logger.error(
                        f"Unexpected error building node for component {yaml_component.get('id', index)}: {e}",
                        exc_info=True,
                    )
                    raise ValueError(f"Failed to build node: {str(e)}")

            logger.info(f"Successfully built {len(nodes)} nodes")
            return nodes

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML: {e}")
            raise ValueError(f"Invalid YAML format: {str(e)}")
        except Exception as e:
            logger.error(f"Error building nodes: {e}", exc_info=True)
            raise
