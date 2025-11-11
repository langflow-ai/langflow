"""Component Resolver for discovering and matching components."""

import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ComponentResolver:
    """Resolves YAML component types to actual Langflow components."""

    def __init__(self):
        """Initialize the component resolver."""
        self._cache: Optional[Dict[str, Any]] = None

    async def fetch_all_components(self) -> Dict[str, Any]:
        """
        Fetch all components from the component catalog.

        This uses the same method as the /api/v1/all endpoint to get
        all available components in Langflow.

        Returns:
            Dict of all components organized by category.
            Example structure:
            {
                "processing": {
                    "Prompt Template": {
                        "template": {"code": {"value": "class PromptComponent..."}},
                        ...
                    }
                },
                "agents": {
                    "Agent": {
                        "template": {"code": {"value": "class AgentComponent..."}},
                        ...
                    }
                }
            }
        """
        try:
            from langflow.interface.components import get_and_cache_all_types_dict
            from langflow.services.deps import get_settings_service

            logger.info("Fetching all components from catalog")
            all_types = await get_and_cache_all_types_dict(settings_service=get_settings_service())

            self._cache = all_types
            logger.info(f"Cached {len(all_types)} component categories")
            return all_types

        except Exception as e:
            logger.error(f"Failed to fetch components: {e}")
            return {}

    def get_cached_components(self) -> Dict[str, Any]:
        """Return the cached component catalog if available, else empty dict.

        This allows downstream validators to reuse the already-fetched catalog
        without re-reading JSON from disk.

        Returns:
            Dict[str, Any]: Cached components by category.
        """
        return self._cache or {}

    def _extract_class_name_from_code(self, comp_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the class name from component's code.value field.

        The component catalog stores the actual Python class code in:
        component_data["template"]["code"]["value"]

        We use regex to find the class name.

        Example:
            code.value = "class PromptComponent(Component):\\n    def build()..."
            Returns: "PromptComponent"

        Example:
            code.value = "class ChatInput(Component):\\n    pass"
            Returns: "ChatInput"

        Args:
            comp_data: Component data dict from catalog

        Returns:
            Class name if found (e.g., "PromptComponent"), None otherwise
        """
        try:
            template = comp_data.get("template", {})
            code_field = template.get("code", {})
            code_value = code_field.get("value", "")

            if not code_value:
                return None

            # Extract first class name using regex
            # Pattern: "class ClassName" or "class ClassName(BaseClass)"
            class_match = re.search(r'class\s+(\w+)', code_value)

            if class_match:
                class_name = class_match.group(1)
                return class_name

            return None

        except Exception as e:
            logger.debug(f"Failed to extract class name: {e}")
            return None

    def find_component(self, yaml_type: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """
        Find component by YAML type (which is the class name).

        Process:
        1. Take the YAML type (e.g., "PromptComponent")
        2. Search all components in the catalog
        3. For each component, extract class name from template.code.value
        4. If class name matches (case-insensitive), return the component

        Example 1:
            Input: yaml_type = "PromptComponent"
            Search catalog → Find "class PromptComponent" in code.value
            Found in: category="processing", component_name="Prompt Template"
            Return: ("processing", "Prompt Template", {...component_data...})

        Example 2:
            Input: yaml_type = "ChatInput"
            Search catalog → Find "class ChatInput" in code.value
            Found in: category="input_output", component_name="ChatInput"
            Return: ("input_output", "ChatInput", {...component_data...})

        Args:
            yaml_type: Type from YAML - this is the CLASS NAME
                      (e.g., "PromptComponent", "AgentComponent", "ChatInput")

        Returns:
            Tuple of (category, catalog_component_name, component_data) if found
            None if not found

            Where:
            - category: The category folder (e.g., "processing", "agents")
            - catalog_component_name: The display name in catalog (e.g., "Prompt Template")
            - component_data: Full component data dict
        """
        if not self._cache:
            logger.warning("Component cache not initialized. Call fetch_all_components() first.")
            return None

        logger.info(f"Searching for component with class name: {yaml_type}")

        # Search all categories
        for category, components in self._cache.items():
            # Search all components in this category
            for comp_name, comp_data in components.items():
                # Extract class name from code.value
                class_name = self._extract_class_name_from_code(comp_data)

                if not class_name:
                    # This component doesn't have a class name in code.value
                    continue

                # Compare: YAML type should match class name (case-insensitive)
                if class_name.lower() == yaml_type.lower():
                    logger.info(f"✓ Found: {yaml_type} → {category}.{comp_name} (class: {class_name})")
                    return (category, comp_name, comp_data)

        # Not found in any category
        logger.warning(f"✗ Component not found: {yaml_type}")
        return None