"""
Dynamic Component Mapper that fetches actual components from Genesis Studio.

This mapper dynamically loads component information from Genesis Studio API
and provides intelligent mapping for genesis: prefixed components.
"""

import json
import os
from typing import Dict, Optional, Any, Set
from datetime import datetime, timedelta
import httpx
import asyncio

from langflow.services.deps import get_settings_service


class DynamicComponentMapper:
    """Maps Genesis component types to actual Genesis Studio components dynamically."""

    def __init__(self):
        self._components_cache: Dict[str, Any] = {}
        self._component_map: Dict[str, str] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_duration = timedelta(hours=1)  # Cache for 1 hour
        self._cache_file = "genesis_components_cache.json"

    async def load_components(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Load components from Genesis Studio API or cache."""
        # Check if we should use cache
        if not force_refresh and self._is_cache_valid():
            return self._components_cache

        try:
            # Try to load from file cache first
            if not force_refresh and os.path.exists(self._cache_file):
                with open(self._cache_file, 'r') as f:
                    cache_data = json.load(f)
                    if 'timestamp' in cache_data:
                        cache_time = datetime.fromisoformat(cache_data['timestamp'])
                        if datetime.now() - cache_time < self._cache_duration:
                            self._components_cache = cache_data['components']
                            self._build_component_map()
                            print(f"✅ Loaded {len(self._get_all_components())} components from cache")
                            return self._components_cache

            # Fetch from API
            settings_service = get_settings_service()
            base_url = f"http://localhost:7860"  # Local API endpoint
            url = f"{base_url}/api/v1/all?force_refresh=true"
            print(f"🔄 Fetching components from Genesis Studio: {url}")

            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    # Handle response
                    components_data = response.json()
                    self._components_cache = components_data
                    self._cache_timestamp = datetime.now()

                    # Save to file cache
                    with open(self._cache_file, 'w') as f:
                        json.dump({
                            'timestamp': self._cache_timestamp.isoformat(),
                            'components': components_data
                        }, f)

                    self._build_component_map()
                    print(f"✅ Loaded {len(self._get_all_components())} components from Genesis Studio API")

                else:
                    print(f"⚠️  Failed to fetch components: {response.status_code}")
                    self._load_fallback_components()

        except Exception as e:
            print(f"⚠️  Error loading components: {e}")
            self._load_fallback_components()

        return self._components_cache

    def _is_cache_valid(self) -> bool:
        """Check if the cache is still valid."""
        if not self._cache_timestamp or not self._components_cache:
            return False
        return datetime.now() - self._cache_timestamp < self._cache_duration

    def _get_all_components(self) -> Dict[str, Dict[str, Any]]:
        """Extract all components from the categorized structure."""
        all_components = {}
        for category, components in self._components_cache.items():
            if isinstance(components, dict):
                all_components.update(components)
        return all_components

    def _build_component_map(self):
        """Build the component mapping for genesis: types."""
        self._component_map = {}
        all_components = self._get_all_components()

        # Build reverse mapping from normalized names to actual component names
        for comp_name in all_components.keys():
            normalized = comp_name.lower().replace('-', '_')
            self._component_map[normalized] = comp_name

        # Add specific mappings for common genesis types
        additional_mappings = {
            "autonomize_agent": "AutonomizeAgent",
            "agent": "AutonomizeAgent",
            "chat_input": "ChatInput",
            "chat_output": "ChatOutput",
            "json_output": "ParseData",
            "prompt_template": "Prompt",
            "conversation_memory": "Memory",
        }

        for key, value in additional_mappings.items():
            if value in all_components:
                self._component_map[key] = value

    def _load_fallback_components(self):
        """Load fallback component mappings when API is unavailable."""
        print("🔄 Loading fallback component mappings...")
        self._component_map = {
            "autonomize_agent": "AutonomizeAgent",
            "agent": "AutonomizeAgent",
            "chat_input": "ChatInput",
            "chat_output": "ChatOutput",
            "json_output": "ParseData",
            "prompt_template": "Prompt",
            "conversation_memory": "Memory",
        }

        # Create minimal components cache for fallback
        self._components_cache = {
            "custom": {
                "ChatInput": {
                    "base_classes": ["Message"],
                    "description": "Chat input component",
                    "display_name": "Chat Input",
                    "outputs": [{"name": "message", "types": ["Message"]}],
                    "template": {}
                },
                "ChatOutput": {
                    "base_classes": ["Message"],
                    "description": "Chat output component",
                    "display_name": "Chat Output",
                    "template": {"input_value": {"required": True, "show": True, "type": "str"}}
                },
                "AutonomizeAgent": {
                    "base_classes": ["Agent"],
                    "description": "Autonomize Agent",
                    "display_name": "Agent",
                    "outputs": [{"name": "response", "types": ["Message"]}],
                    "template": {}
                }
            }
        }

    def get_component_type(self, genesis_type: str) -> str:
        """
        Get the actual Genesis Studio component type for a genesis: prefixed type.

        Args:
            genesis_type: Component type (e.g., "genesis:autonomize_agent")

        Returns:
            Actual Genesis Studio component type
        """
        # Remove genesis: prefix if present
        if genesis_type.startswith("genesis:"):
            base_type = genesis_type[8:]  # Remove "genesis:"
        else:
            base_type = genesis_type

        # Normalize the type
        normalized = base_type.lower().replace('-', '_')

        # Direct mapping check
        if normalized in self._component_map:
            return self._component_map[normalized]

        # Intelligent mapping based on type patterns
        mapping_rules = {
            # Autonomize-specific components
            "autonomize_agent": "AutonomizeAgent",
            "agent": "AutonomizeAgent",

            # Input/Output components
            "chat_input": "ChatInput",
            "chat_output": "ChatOutput",
            "text_input": "TextInput",
            "json_output": "ParseData",

            # AI components
            "prompt_template": "Prompt",
            "llm": "ChatOpenAI",

            # Memory components
            "conversation_memory": "Memory",
            "chat_memory": "Memory",
        }

        if normalized in mapping_rules:
            return mapping_rules[normalized]

        # Pattern-based intelligent mapping
        if "agent" in normalized:
            return "AutonomizeAgent"
        elif "input" in normalized:
            return "ChatInput"
        elif "output" in normalized:
            return "ChatOutput"
        elif "prompt" in normalized:
            return "Prompt"
        elif "memory" in normalized:
            return "Memory"
        elif any(term in normalized for term in ["llm", "model", "openai", "anthropic"]):
            return "ChatOpenAI"
        else:
            return "CustomComponent"

    def get_component_data(self, component_type: str) -> Optional[Dict[str, Any]]:
        """Get the full component data for a component type."""
        # First try to find in cache
        for category, components in self._components_cache.items():
            if isinstance(components, dict) and component_type in components:
                return components[component_type]
        return None

    def get_component_category(self, component_type: str) -> str:
        """Get the category for a component type."""
        for category, components in self._components_cache.items():
            if isinstance(components, dict) and component_type in components:
                return category
        return "custom"

    def is_component_available(self, component_type: str) -> bool:
        """Check if a component type is available."""
        mapped_type = self.get_component_type(component_type)
        available = self.get_available_components()
        return mapped_type in available

    def get_available_components(self) -> Set[str]:
        """Get set of all available component names."""
        return set(self._get_all_components().keys())


# Global instance
_mapper_instance: Optional[DynamicComponentMapper] = None


async def get_dynamic_mapper() -> DynamicComponentMapper:
    """Get or create the global dynamic mapper instance."""
    global _mapper_instance

    if _mapper_instance is None:
        _mapper_instance = DynamicComponentMapper()
        await _mapper_instance.load_components()

    return _mapper_instance


def get_langflow_component_type(genesis_type: str) -> str:
    """
    Synchronous wrapper for getting component type.
    Falls back to intelligent mapping if async mapper not available.
    """
    # If we have a cached mapper, use it
    if _mapper_instance:
        return _mapper_instance.get_component_type(genesis_type)

    # Otherwise use static intelligent mapping
    if genesis_type.startswith("genesis:"):
        base_type = genesis_type[8:]
    else:
        base_type = genesis_type

    # Intelligent static mapping
    static_map = {
        "autonomize_agent": "AutonomizeAgent",
        "chat_input": "ChatInput",
        "chat_output": "ChatOutput",
        "json_output": "ParseData",
        "prompt_template": "Prompt",
        "conversation_memory": "Memory",
    }

    normalized = base_type.lower().replace('-', '_')
    if normalized in static_map:
        return static_map[normalized]

    # Pattern-based fallback
    if "agent" in normalized:
        return "AutonomizeAgent"
    elif any(term in normalized for term in ["tool", "component", "model", "llm"]):
        return "CustomComponent"
    else:
        return "CustomComponent"