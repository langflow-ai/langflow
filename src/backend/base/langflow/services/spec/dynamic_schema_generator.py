"""
Dynamic Schema Generator for Component Validation.

This module generates validation schemas dynamically for components discovered at runtime,
addressing the issue of missing schemas for 300+ dynamically discovered components.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DynamicSchemaGenerator:
    """Generate validation schemas dynamically based on component metadata."""

    def __init__(self):
        """Initialize the dynamic schema generator."""
        self._schema_cache: Dict[str, Dict] = {}
        self._generation_stats = {
            "total_generated": 0,
            "cache_hits": 0,
            "generation_failures": 0
        }

    def generate_schema_from_introspection(
        self,
        genesis_type: str,
        component_category: str,
        introspection_data: Optional[Dict] = None,
        base_config: Optional[Dict] = None,
        tool_capabilities: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Generate a validation schema based on component introspection data.

        Args:
            genesis_type: Component type (e.g., 'genesis:agent')
            component_category: Category (e.g., 'agent', 'tool', 'healthcare')
            introspection_data: Runtime introspection data
            base_config: Base configuration
            tool_capabilities: Tool capability information

        Returns:
            Generated JSON schema for component validation
        """
        # Check cache first
        if genesis_type in self._schema_cache:
            self._generation_stats["cache_hits"] += 1
            return self._schema_cache[genesis_type]

        try:
            # Generate schema based on category
            schema = self._generate_base_schema(genesis_type, component_category)

            # Enhance with introspection data
            if introspection_data:
                schema = self._enhance_with_introspection(schema, introspection_data)

            # Add tool-specific properties
            if tool_capabilities:
                schema = self._enhance_with_tool_capabilities(schema, tool_capabilities)

            # Add category-specific properties
            schema = self._add_category_specific_properties(schema, component_category, genesis_type)

            # Cache the generated schema
            self._schema_cache[genesis_type] = schema
            self._generation_stats["total_generated"] += 1

            logger.debug(f"Generated dynamic schema for {genesis_type}")
            return schema

        except Exception as e:
            logger.warning(f"Failed to generate schema for {genesis_type}: {e}")
            self._generation_stats["generation_failures"] += 1
            return self._get_fallback_schema()

    def _generate_base_schema(self, genesis_type: str, category: str) -> Dict[str, Any]:
        """Generate base schema structure."""
        return {
            "type": "object",
            "description": f"Dynamic schema for {genesis_type} ({category} component)",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Component instance name"
                },
                "description": {
                    "type": "string",
                    "description": "Component description"
                }
            },
            "additionalProperties": True  # Allow additional properties for flexibility
        }

    def _enhance_with_introspection(self, schema: Dict, introspection: Dict) -> Dict:
        """Enhance schema with introspection data."""
        # Check for specific methods or interfaces
        if introspection.get("has_build_method"):
            schema["properties"]["build_config"] = {
                "type": "object",
                "description": "Build configuration"
            }

        if introspection.get("has_as_tool_method"):
            schema["properties"]["tool_mode"] = {
                "type": "boolean",
                "default": False,
                "description": "Enable tool mode"
            }

        # Add properties based on base classes
        base_classes = introspection.get("base_classes", [])
        if any("connector" in cls.lower() for cls in base_classes):
            schema["properties"]["connection_config"] = {
                "type": "object",
                "description": "Connection configuration"
            }

        return schema

    def _enhance_with_tool_capabilities(self, schema: Dict, capabilities: Dict) -> Dict:
        """Enhance schema with tool capability information."""
        if capabilities.get("accepts_tools"):
            schema["properties"]["tools"] = {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of tool identifiers"
            }

        if capabilities.get("provides_tools"):
            schema["properties"]["tool_output_config"] = {
                "type": "object",
                "description": "Tool output configuration"
            }

        return schema

    def _add_category_specific_properties(self, schema: Dict, category: str, genesis_type: str) -> Dict:
        """Add category-specific properties to schema."""

        # Healthcare components
        if category == "healthcare" or "healthcare" in genesis_type:
            schema["properties"].update({
                "hipaa_compliant": {
                    "type": "boolean",
                    "default": True,
                    "description": "HIPAA compliance flag"
                },
                "phi_handling": {
                    "type": "string",
                    "enum": ["none", "masked", "encrypted"],
                    "default": "masked",
                    "description": "PHI data handling method"
                }
            })

        # Agent components
        elif category == "agent":
            schema["properties"].update({
                "max_iterations": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": "Maximum agent iterations"
                },
                "temperature": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 2,
                    "default": 0.7,
                    "description": "Model temperature"
                }
            })

        # Tool components
        elif category == "tool":
            schema["properties"].update({
                "timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 300,
                    "default": 30,
                    "description": "Tool execution timeout"
                },
                "retry_count": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 5,
                    "default": 3,
                    "description": "Retry count on failure"
                }
            })

        # LLM components
        elif category == "llm":
            schema["properties"].update({
                "model": {
                    "type": "string",
                    "description": "Model identifier"
                },
                "api_key": {
                    "type": "string",
                    "description": "API key for model access"
                },
                "max_tokens": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 32768,
                    "default": 1000,
                    "description": "Maximum tokens"
                }
            })

        # Vector store components
        elif category == "vector_store":
            schema["properties"].update({
                "collection_name": {
                    "type": "string",
                    "description": "Vector collection name"
                },
                "dimension": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 4096,
                    "description": "Vector dimensions"
                },
                "similarity_metric": {
                    "type": "string",
                    "enum": ["cosine", "euclidean", "dot_product"],
                    "default": "cosine",
                    "description": "Similarity metric"
                }
            })

        # Data processing components
        elif category == "data":
            schema["properties"].update({
                "batch_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10000,
                    "default": 100,
                    "description": "Batch processing size"
                },
                "data_format": {
                    "type": "string",
                    "enum": ["json", "csv", "xml", "text"],
                    "default": "json",
                    "description": "Data format"
                }
            })

        # IO components
        elif category == "io":
            schema["properties"].update({
                "input_type": {
                    "type": "string",
                    "description": "Input data type"
                },
                "output_type": {
                    "type": "string",
                    "description": "Output data type"
                },
                "validation": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable input validation"
                }
            })

        # Memory components
        elif category == "memory":
            schema["properties"].update({
                "memory_type": {
                    "type": "string",
                    "enum": ["buffer", "summary", "conversation", "entity"],
                    "default": "conversation",
                    "description": "Memory storage type"
                },
                "max_memory_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 100,
                    "description": "Maximum memory entries"
                }
            })

        # Prompt components
        elif category == "prompt":
            schema["properties"].update({
                "template": {
                    "type": "string",
                    "description": "Prompt template"
                },
                "variables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Template variables"
                }
            })

        # Embedding components
        elif category == "embedding":
            schema["properties"].update({
                "embedding_model": {
                    "type": "string",
                    "description": "Embedding model name"
                },
                "embedding_dimension": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 4096,
                    "description": "Embedding vector dimension"
                }
            })

        return schema

    def _get_fallback_schema(self) -> Dict[str, Any]:
        """Get minimal fallback schema for failed generation."""
        return {
            "type": "object",
            "description": "Fallback schema - allows any valid object",
            "additionalProperties": True
        }

    def generate_schemas_for_components(
        self,
        components: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate schemas for multiple components.

        Args:
            components: List of component metadata dictionaries

        Returns:
            Dictionary mapping genesis_type to generated schema
        """
        schemas = {}

        for component in components:
            genesis_type = component.get("genesis_type")
            if not genesis_type:
                continue

            schema = self.generate_schema_from_introspection(
                genesis_type=genesis_type,
                component_category=component.get("component_category", "general"),
                introspection_data=component.get("introspection_data"),
                base_config=component.get("base_config"),
                tool_capabilities=component.get("tool_capabilities")
            )

            schemas[genesis_type] = schema

        return schemas

    def get_generation_stats(self) -> Dict[str, Any]:
        """Get schema generation statistics."""
        return {
            **self._generation_stats,
            "cache_size": len(self._schema_cache),
            "cached_types": list(self._schema_cache.keys())[:10]  # First 10 for brevity
        }

    def clear_cache(self):
        """Clear the schema cache."""
        self._schema_cache.clear()
        logger.info("Cleared dynamic schema cache")


# Singleton instance
_generator_instance = None


def get_dynamic_schema_generator() -> DynamicSchemaGenerator:
    """Get singleton instance of dynamic schema generator."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = DynamicSchemaGenerator()
    return _generator_instance


def generate_dynamic_schema(
    genesis_type: str,
    component_category: str = "general",
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to generate a dynamic schema.

    Args:
        genesis_type: Component type
        component_category: Component category
        **kwargs: Additional metadata for schema generation

    Returns:
        Generated validation schema
    """
    generator = get_dynamic_schema_generator()
    return generator.generate_schema_from_introspection(
        genesis_type=genesis_type,
        component_category=component_category,
        **kwargs
    )