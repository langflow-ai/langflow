"""Config Builder - Adds configuration to flow nodes."""

import logging
from typing import Any, Dict, List, Tuple

import yaml

logger = logging.getLogger(__name__)


class ConfigBuilder:
    """
    Builds and applies configuration to flow nodes.

    This class is responsible for:
    - Extracting config from YAML components
    - Mapping config values to node templates
    - Validating config against component schemas
    - Type conversion and validation
    """

    def __init__(self, all_components: Dict[str, Any]):
        """
        Initialize the ConfigBuilder.

        Args:
            all_components: Component catalog from get_and_cache_all_types_dict()
                           Structure: {category: {component_name: component_data}}
        """
        self.all_components = all_components
        logger.info("ConfigBuilder initialized")

    def _validate_and_convert_value(self, input_type: str, yaml_value: Any, existing_value: Any = None) -> Tuple[bool, Any]:
        """
        Validate and convert YAML value based on template field _input_type.

        Args:
            input_type: The _input_type from template field (e.g., "IntInput", "BoolInput")
            yaml_value: The value from YAML config
            existing_value: The existing value from the template field (for merging with defaults)

        Returns:
            Tuple of (is_valid, converted_value)
            - is_valid: True if value is valid for the input type
            - converted_value: The value converted to the appropriate type, or None if invalid
        """
        try:
            # Integer inputs
            if input_type == "IntInput":
                if isinstance(yaml_value, int) and not isinstance(yaml_value, bool):
                    return True, yaml_value
                try:
                    return True, int(yaml_value)
                except (ValueError, TypeError):
                    return False, None

            # Float inputs
            elif input_type == "FloatInput":
                if isinstance(yaml_value, float):
                    return True, yaml_value
                if isinstance(yaml_value, int) and not isinstance(yaml_value, bool):
                    return True, float(yaml_value)
                try:
                    return True, float(yaml_value)
                except (ValueError, TypeError):
                    return False, None

            # Boolean inputs
            elif input_type == "BoolInput":
                if isinstance(yaml_value, bool):
                    return True, yaml_value
                if isinstance(yaml_value, str):
                    if yaml_value.lower() in ["true", "1", "yes"]:
                        return True, True
                    if yaml_value.lower() in ["false", "0", "no"]:
                        return True, False
                if isinstance(yaml_value, int):
                    return True, bool(yaml_value)
                return False, None

            # Slider inputs (number/float)
            elif input_type == "SliderInput":
                if isinstance(yaml_value, (int, float)) and not isinstance(yaml_value, bool):
                    return True, float(yaml_value)
                try:
                    return True, float(yaml_value)
                except (ValueError, TypeError):
                    return False, None

            # String-based inputs
            elif input_type in [
                "StrInput",
                "MessageInput",
                "MessageTextInput",
                "MultilineInput",
                "SecretStrInput",
                "MultilineSecretInput",
                "DropdownInput",
                "TabInput",
                "QueryInput",
                "FileInput",
                "PromptInput",
                "HandleInput",
                "ConnectionInput",
                "AuthInput",
                "DataFrameInput",
                "SortableListInput",
            ]:
                if isinstance(yaml_value, str):
                    return True, yaml_value
                # Convert to string
                return True, str(yaml_value)

            # Dictionary inputs
            elif input_type in ["DictInput", "NestedDictInput", "McpInput"]:
                if isinstance(yaml_value, dict):
                    return True, yaml_value
                return False, None

            # Table/Array inputs
            elif input_type in ["TableInput", "DataInput"]:
                if isinstance(yaml_value, list):
                    # For TableInput, merge with existing defaults if available
                    if input_type == "TableInput" and existing_value and isinstance(existing_value, list):
                        # Create dict from existing values
                        merged_dict = {}
                        for item in existing_value:
                            if isinstance(item, dict) and "key" in item and "value" in item:
                                merged_dict[item["key"]] = item["value"]

                        # Merge with YAML values (YAML overrides defaults)
                        for item in yaml_value:
                            if isinstance(item, dict) and "key" in item and "value" in item:
                                merged_dict[item["key"]] = item["value"]

                        # Convert back to list format
                        logger.debug(f"Merged TableInput: {len(existing_value)} existing + {len(yaml_value)} YAML = {len(merged_dict)} total items")
                        return True, [{"key": k, "value": v} for k, v in merged_dict.items()]

                    # For DataInput or TableInput without defaults, just return the list
                    return True, yaml_value
                return False, None

            # Multiselect (array of strings)
            elif input_type == "MultiselectInput":
                if isinstance(yaml_value, list):
                    # Ensure all items are strings
                    return True, [str(item) for item in yaml_value]
                if isinstance(yaml_value, str):
                    # Single value, wrap in array
                    return True, [yaml_value]
                return False, None

            # Unknown input type - fallback to string
            else:
                logger.warning(f"Unknown _input_type '{input_type}', treating as string")
                if isinstance(yaml_value, str):
                    return True, yaml_value
                return True, str(yaml_value)

        except Exception as e:
            logger.error(f"Error validating/converting value for input_type {input_type}: {e}")
            return False, None

    def _find_yaml_component_by_id(
        self, node: Dict[str, Any], yaml_components: List[Dict[str, Any]]
    ) -> Dict[str, Any] | None:
        """
        Find YAML component by the ID stored in node data.

        Args:
            node: Node dictionary with yaml_component_id in data
            yaml_components: List of YAML components

        Returns:
            Matching YAML component dictionary or None if not found
        """
        # Get the stored YAML component ID from node
        yaml_comp_id = node.get("data", {}).get("yaml_component_id")

        if not yaml_comp_id:
            logger.warning(f"Node {node.get('id')} has no yaml_component_id")
            return None

        # Find matching YAML component
        for yaml_comp in yaml_components:
            if yaml_comp.get("id") == yaml_comp_id:
                return yaml_comp

        logger.warning(f"Could not find YAML component with id: {yaml_comp_id}")
        return None

    def _apply_config_to_node(self, node: Dict[str, Any], yaml_component: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply config from YAML component to node template.

        Args:
            node: Node dictionary to modify
            yaml_component: YAML component with config section

        Returns:
            Modified node dictionary
        """
        config = yaml_component.get("config", {})
        if not config:
            logger.debug(f"No config found for component {yaml_component.get('id')}")
            return node

        # Get template from node
        template = node.get("data", {}).get("node", {}).get("template", {})
        if not template:
            logger.warning(f"No template found in node {node.get('id')}")
            return node

        component_id = yaml_component.get("id", "unknown")
        config_applied_count = 0

        # Apply each config key-value pair
        for config_key, config_value in config.items():
            # Check if field exists in template
            if config_key not in template:
                logger.warning(
                    f"Config key '{config_key}' not found in template for component '{component_id}'. "
                    f"Available keys: {list(template.keys())[:10]}..."
                )
                continue

            # Get field metadata
            field = template[config_key]
            input_type = field.get("_input_type", "StrInput")  # Default to StrInput if not found
            existing_value = field.get("value")  # Get existing value for merging

            # Validate and convert value
            is_valid, converted_value = self._validate_and_convert_value(input_type, config_value, existing_value)

            if not is_valid:
                logger.warning(
                    f"Invalid value type for '{config_key}' in component '{component_id}': "
                    f"expected {input_type}, got {type(config_value).__name__}. Value: {config_value}"
                )
                continue

            # Set the value in the template
            field["value"] = converted_value

            # Mark as user-configured to prevent component updates from overwriting
            field["user_configured"] = True
            field["configured_from_spec"] = True

            # Special handling for DropdownInput to preserve dropdown properties
            if input_type == "DropdownInput":
                # The template already contains options, options_metadata, combobox, etc.
                # We only update the value, keeping all other dropdown properties intact

                # Optional: Validate that the configured value is valid for this dropdown
                options = field.get("options", [])
                is_combobox = field.get("combobox", False)

                # Only validate if options exist and combobox is disabled (strict dropdown)
                if options and not is_combobox and converted_value not in options:
                    logger.warning(
                        f"Value '{converted_value}' for '{config_key}' in component '{component_id}' "
                        f"is not in the available options: {options}. "
                        f"This may cause issues unless combobox mode is enabled."
                    )

                logger.debug(
                    f"Preserved dropdown properties for '{config_key}': "
                    f"options={len(options)} items, combobox={is_combobox}"
                )

            # Set advanced to false for any field configured in YAML
            if "advanced" in field:
                field["advanced"] = False
                logger.debug(f"Set advanced=false for configured field '{config_key}' in component '{component_id}'")
            
            config_applied_count += 1
            logger.debug(
                f"Applied config to '{component_id}.{config_key}': "
                f"{repr(converted_value)[:100]} (input_type: {input_type})"
            )

        logger.info(f"Applied {config_applied_count}/{len(config)} config values to component '{component_id}'")

        return node

    def _process_prompt_template_fields(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process PromptComponent nodes to create dynamic template fields.

        Extracts {variables} from template string and creates corresponding input fields
        automatically. This replicates the behavior of PromptComponent.update_frontend_node()
        which is normally called in the UI but bypassed during YAML import.

        Args:
            node: Node dictionary with template

        Returns:
            Modified node with dynamic template fields created
        """
        from langflow.base.prompts.api_utils import process_prompt_template

        # Only process PromptComponent nodes
        node_type = node.get("data", {}).get("type")
        if node_type not in ["PromptComponent", "Prompt"]:
            return node

        # Get node objects
        node_obj = node.get("data", {}).get("node", {})
        template_dict = node_obj.get("template", {})

        # Get template string value
        template_value = template_dict.get("template", {}).get("value", "")
        if not template_value:
            logger.debug(f"No template value found for node {node.get('id')}, skipping field creation")
            return node

        # Initialize custom_fields if not exists
        custom_fields = node_obj.get("custom_fields", {})
        if not custom_fields:
            custom_fields = {"template": []}
            node_obj["custom_fields"] = custom_fields

        # Call process_prompt_template to extract variables and create fields
        try:
            input_variables = process_prompt_template(
                template=template_value,
                name="template",
                custom_fields=custom_fields,
                frontend_node_template=template_dict
            )
            logger.info(
                f"Created {len(input_variables)} dynamic template fields for node {node.get('id')}: "
                f"{input_variables}"
            )
        except Exception as e:
            logger.error(
                f"Error processing prompt template for node {node.get('id')}: {e}",
                exc_info=True
            )
            # Don't fail the entire import, just log the error

        return node

    async def apply_config(self, nodes: List[Dict[str, Any]], yaml_content: str) -> List[Dict[str, Any]]:
        """
        Apply configuration to nodes from YAML specification.

        This method:
        1. Parses the YAML to extract components with configs
        2. Matches each node to its YAML component by ID
        3. Applies config values to node template fields
        4. Validates types and converts values as needed

        Args:
            nodes: List of node dictionaries from NodeBuilder
            yaml_content: YAML specification content

        Returns:
            List of nodes with configuration applied

        Raises:
            ValueError: If YAML parsing fails or configuration is invalid
        """
        logger.info(f"Applying configuration to {len(nodes)} nodes")

        try:
            # Parse YAML to get components
            spec = yaml.safe_load(yaml_content)
            yaml_components = spec.get("components", [])

            if not yaml_components:
                logger.warning("No components found in YAML specification")
                return nodes

            logger.info(f"Found {len(yaml_components)} components in YAML")

            # Apply config to each node
            configured_nodes = []
            nodes_with_config = 0

            for node in nodes:
                # Find matching YAML component by ID
                yaml_comp = self._find_yaml_component_by_id(node, yaml_components)

                if not yaml_comp:
                    logger.warning(f"Could not find YAML component for node {node.get('id')}")
                    configured_nodes.append(node)
                    continue

                # Check if component has config
                if not yaml_comp.get("config"):
                    logger.debug(f"No config to apply for component {yaml_comp.get('id')}")
                    configured_nodes.append(node)
                    continue

                # Apply config to node
                configured_node = self._apply_config_to_node(node, yaml_comp)
                configured_nodes.append(configured_node)
                nodes_with_config += 1

            logger.info(f"Configuration applied to {nodes_with_config}/{len(nodes)} nodes")

            # POST-PROCESSING: Create dynamic template fields for PromptComponents
            logger.info("Post-processing: Creating dynamic template fields for PromptComponents")
            final_nodes = []
            for node in configured_nodes:
                processed_node = self._process_prompt_template_fields(node)
                final_nodes.append(processed_node)

            return final_nodes

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML: {e}")
            raise ValueError(f"Invalid YAML format: {str(e)}")
        except Exception as e:
            logger.error(f"Error applying config: {e}", exc_info=True)
            raise ValueError(f"Failed to apply configuration: {str(e)}")
