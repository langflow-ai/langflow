"""Dynamic component discovery service for automatic component mapping."""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.base import Service
from langflow.services.spec.component_schema_inspector import ComponentSchemaInspector, ComponentSchema
from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentCategoryEnum,
)
from langflow.services.database.models.component_mapping.runtime_adapter import (
    RuntimeAdapter,
    RuntimeAdapterCreate,
    RuntimeTypeEnum,
)
from langflow.services.component_mapping.service import ComponentMappingService

logger = logging.getLogger(__name__)


class ComponentDiscoveryService(Service):
    """Service for discovering and managing dynamic component mappings."""

    name = "component_discovery_service"

    def __init__(self):
        """Initialize the component discovery service."""
        super().__init__()
        self._inspector: Optional[ComponentSchemaInspector] = None
        self._mapping_service: Optional[ComponentMappingService] = None

    @property
    def inspector(self) -> ComponentSchemaInspector:
        """Get component schema inspector instance (lazy loaded)."""
        if self._inspector is None:
            self._inspector = ComponentSchemaInspector()
        return self._inspector

    @property
    def mapping_service(self) -> ComponentMappingService:
        """Get component mapping service instance (lazy loaded)."""
        if self._mapping_service is None:
            self._mapping_service = ComponentMappingService()
        return self._mapping_service

    async def discover_components(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Discover all available Langflow components and analyze mapping gaps.

        Returns:
            Dictionary with discovery results including new components found
        """
        logger.info("Starting component discovery process...")

        try:
            # Get all component schemas from Langflow
            all_schemas = self.inspector.get_all_schemas()
            logger.info(f"Discovered {len(all_schemas)} Langflow components")

            # Get existing mappings from database
            existing_mappings = await self.mapping_service.get_all_component_mappings(
                session, active_only=False
            )
            existing_components = {self._extract_component_name(m.io_mapping): m for m in existing_mappings
                                 if m.io_mapping and m.io_mapping.get("component")}

            # Analyze gaps and opportunities
            discovery_results = {
                "total_langflow_components": len(all_schemas),
                "existing_mappings": len(existing_mappings),
                "new_components_found": [],
                "updated_schemas": [],
                "mapping_recommendations": [],
                "statistics": {},
            }

            for component_name, schema in all_schemas.items():
                if component_name not in existing_components:
                    # New component discovered
                    recommendation = self._create_mapping_recommendation(schema)
                    discovery_results["new_components_found"].append({
                        "component_name": component_name,
                        "schema": self._schema_to_dict(schema),
                        "recommendation": recommendation,
                    })
                else:
                    # Existing component - check for schema updates
                    existing_mapping = existing_components[component_name]
                    if self._has_schema_changed(existing_mapping, schema):
                        discovery_results["updated_schemas"].append({
                            "component_name": component_name,
                            "existing_mapping_id": str(existing_mapping.id),
                            "schema_changes": self._detect_schema_changes(existing_mapping, schema),
                        })

            # Generate statistics
            discovery_results["statistics"] = self._generate_discovery_statistics(
                all_schemas, existing_mappings
            )

            # Generate high-priority mapping recommendations
            discovery_results["mapping_recommendations"] = self._generate_mapping_recommendations(
                discovery_results["new_components_found"]
            )

            logger.info(f"Discovery complete: {len(discovery_results['new_components_found'])} new components found")
            return discovery_results

        except Exception as e:
            logger.error(f"Error during component discovery: {e}")
            return {"error": str(e)}

    async def auto_create_mappings(
        self,
        session: AsyncSession,
        component_names: List[str],
        genesis_type_prefix: str = "genesis:",
    ) -> Dict[str, Any]:
        """
        Automatically create mappings for discovered components.

        Args:
            session: Database session
            component_names: List of component names to create mappings for
            genesis_type_prefix: Prefix for generated genesis types

        Returns:
            Results of mapping creation process
        """
        results = {
            "created": 0,
            "errors": [],
            "created_mappings": [],
        }

        all_schemas = self.inspector.get_all_schemas()

        for component_name in component_names:
            if component_name not in all_schemas:
                results["errors"].append(f"Component {component_name} not found")
                continue

            try:
                schema = all_schemas[component_name]

                # Generate genesis type name
                genesis_type = self._generate_genesis_type_name(component_name, genesis_type_prefix)

                # Check if mapping already exists
                existing = await self.mapping_service.get_component_mapping_by_genesis_type(
                    session, genesis_type, active_only=False
                )

                if existing:
                    results["errors"].append(f"Mapping for {genesis_type} already exists")
                    continue

                # Create component mapping
                mapping_data = ComponentMappingCreate(
                    genesis_type=genesis_type,
                    base_config=self._extract_default_config(schema),
                    io_mapping=self._create_io_mapping_from_schema(schema),
                    component_category=self._determine_component_category(schema),
                    description=f"Auto-generated mapping for {component_name}",
                    version="1.0.0",
                    active=True,
                )

                created_mapping = await self.mapping_service.create_component_mapping(
                    session, mapping_data
                )

                # Create Langflow runtime adapter
                adapter_data = RuntimeAdapterCreate(
                    genesis_type=genesis_type,
                    runtime_type=RuntimeTypeEnum.LANGFLOW,
                    target_component=component_name,
                    adapter_config=self._extract_adapter_config(schema),
                    version="1.0.0",
                    description=f"Auto-generated Langflow adapter for {component_name}",
                    active=True,
                    priority=200,  # Lower priority than manually created mappings
                )

                await self.mapping_service.create_runtime_adapter(session, adapter_data)

                results["created"] += 1
                results["created_mappings"].append({
                    "genesis_type": genesis_type,
                    "component_name": component_name,
                    "mapping_id": str(created_mapping.id),
                })

                logger.info(f"Created auto-mapping: {genesis_type} -> {component_name}")

            except Exception as e:
                logger.error(f"Error creating mapping for {component_name}: {e}")
                results["errors"].append(f"{component_name}: {str(e)}")

        return results

    async def update_schemas_from_discovery(
        self,
        session: AsyncSession,
        force_update: bool = False,
    ) -> Dict[str, Any]:
        """
        Update existing component mappings with latest schema information.

        Args:
            session: Database session
            force_update: Whether to force update even if no changes detected

        Returns:
            Results of schema update process
        """
        results = {
            "updated": 0,
            "errors": [],
            "no_changes": 0,
        }

        try:
            all_schemas = self.inspector.get_all_schemas()
            existing_mappings = await self.mapping_service.get_all_component_mappings(
                session, active_only=True
            )

            for mapping in existing_mappings:
                if not mapping.io_mapping or not mapping.io_mapping.get("component"):
                    continue

                component_name = self._extract_component_name(mapping.io_mapping)
                if component_name not in all_schemas:
                    continue

                schema = all_schemas[component_name]

                if force_update or self._has_schema_changed(mapping, schema):
                    try:
                        # Update I/O mapping with latest schema
                        updated_io_mapping = self._create_io_mapping_from_schema(schema)

                        # Preserve existing mapping data, only update discovered schema parts
                        updated_io_mapping.update({
                            k: v for k, v in mapping.io_mapping.items()
                            if k not in ["input_field", "output_field", "input_types", "output_types"]
                        })

                        from langflow.services.database.models.component_mapping import ComponentMappingUpdate
                        update_data = ComponentMappingUpdate(
                            io_mapping=updated_io_mapping,
                            description=f"Schema updated via discovery: {mapping.description or ''}".strip(),
                        )

                        await self.mapping_service.update_component_mapping(
                            session, mapping.id, update_data
                        )

                        results["updated"] += 1
                        logger.info(f"Updated schema for {mapping.genesis_type}")

                    except Exception as e:
                        logger.error(f"Error updating schema for {mapping.genesis_type}: {e}")
                        results["errors"].append(f"{mapping.genesis_type}: {str(e)}")
                else:
                    results["no_changes"] += 1

        except Exception as e:
            logger.error(f"Error during schema update: {e}")
            results["errors"].append(f"General error: {str(e)}")

        return results

    def _extract_component_name(self, io_mapping: Optional[Dict]) -> Optional[str]:
        """Extract component name from I/O mapping."""
        if not io_mapping:
            return None
        return io_mapping.get("component")

    def _schema_to_dict(self, schema: ComponentSchema) -> Dict[str, Any]:
        """Convert ComponentSchema to dictionary."""
        return {
            "name": schema.name,
            "class_name": schema.class_name,
            "module_path": schema.module_path,
            "description": schema.description,
            "display_name": schema.display_name,
            "input_types": schema.input_types,
            "output_types": schema.output_types,
            "inputs": schema.inputs,
            "outputs": schema.outputs,
            "base_classes": schema.base_classes,
        }

    def _create_mapping_recommendation(self, schema: ComponentSchema) -> Dict[str, Any]:
        """Create a mapping recommendation for a new component."""
        return {
            "suggested_genesis_type": self._generate_genesis_type_name(schema.name),
            "category": self._determine_component_category(schema),
            "priority": self._assess_mapping_priority(schema),
            "rationale": self._generate_mapping_rationale(schema),
        }

    def _generate_genesis_type_name(self, component_name: str, prefix: str = "genesis:") -> str:
        """Generate a genesis type name from component name."""
        # Convert CamelCase to snake_case
        import re
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', component_name).lower()

        # Remove common suffixes
        name = re.sub(r'_(component|tool|model)$', '', name)

        return f"{prefix}{name}"

    def _determine_component_category(self, schema: ComponentSchema) -> ComponentCategoryEnum:
        """Determine component category from schema."""
        name_lower = schema.name.lower()
        class_name_lower = schema.class_name.lower()
        description_lower = schema.description.lower()

        # Check for healthcare patterns
        if any(term in name_lower for term in ["health", "medical", "clinical", "ehr", "fhir"]):
            return ComponentCategoryEnum.HEALTHCARE

        # Check for agent patterns
        if any(term in name_lower for term in ["agent", "crew"]):
            return ComponentCategoryEnum.AGENT

        # Check for LLM patterns
        if any(term in name_lower for term in ["model", "llm", "openai", "anthropic", "language"]):
            return ComponentCategoryEnum.LLM

        # Check for tool patterns
        if any(term in name_lower for term in ["tool", "calculator", "search", "api"]):
            return ComponentCategoryEnum.TOOL

        # Check for I/O patterns
        if any(term in name_lower for term in ["input", "output", "chat"]):
            return ComponentCategoryEnum.IO

        # Check for prompt patterns
        if any(term in name_lower for term in ["prompt", "template"]):
            return ComponentCategoryEnum.PROMPT

        # Check for memory patterns
        if any(term in name_lower for term in ["memory", "conversation"]):
            return ComponentCategoryEnum.MEMORY

        # Check for embedding patterns
        if any(term in name_lower for term in ["embedding", "embed"]):
            return ComponentCategoryEnum.EMBEDDING

        # Check for vector store patterns
        if any(term in name_lower for term in ["vector", "store", "qdrant", "chroma"]):
            return ComponentCategoryEnum.VECTOR_STORE

        # Check for data processing patterns
        if any(term in name_lower for term in ["data", "csv", "json", "parse", "transform"]):
            return ComponentCategoryEnum.DATA

        # Check for integration patterns
        if any(term in name_lower for term in ["integration", "connector", "webhook"]):
            return ComponentCategoryEnum.INTEGRATION

        # Default to processing for unclassified components
        return ComponentCategoryEnum.PROCESSING

    def _assess_mapping_priority(self, schema: ComponentSchema) -> str:
        """Assess priority for creating mapping based on component characteristics."""
        name_lower = schema.name.lower()

        # High priority: Common components, healthcare, agents
        if any(term in name_lower for term in ["health", "agent", "model", "input", "output"]):
            return "high"

        # Medium priority: Tools, processing, data components
        if any(term in name_lower for term in ["tool", "process", "data", "transform"]):
            return "medium"

        # Low priority: Specialized or rarely used components
        return "low"

    def _generate_mapping_rationale(self, schema: ComponentSchema) -> str:
        """Generate rationale for why this component should be mapped."""
        category = self._determine_component_category(schema)
        priority = self._assess_mapping_priority(schema)

        rationale_parts = [f"Component category: {category.value}"]

        if priority == "high":
            rationale_parts.append("High priority due to common usage patterns")
        elif priority == "medium":
            rationale_parts.append("Medium priority for workflow enhancement")
        else:
            rationale_parts.append("Low priority for specialized use cases")

        if schema.input_types:
            rationale_parts.append(f"Accepts input types: {', '.join(schema.input_types)}")

        if schema.output_types:
            rationale_parts.append(f"Produces output types: {', '.join(schema.output_types)}")

        return "; ".join(rationale_parts)

    def _has_schema_changed(self, mapping: ComponentMapping, schema: ComponentSchema) -> bool:
        """Check if component schema has changed since mapping was created."""
        if not mapping.io_mapping:
            return True

        current_io = mapping.io_mapping

        # Compare input/output types
        if current_io.get("input_types") != schema.input_types:
            return True

        if current_io.get("output_types") != schema.output_types:
            return True

        # Compare field information
        if len(schema.inputs) > 0 and current_io.get("input_field") != schema.inputs[0].get("name"):
            return True

        if len(schema.outputs) > 0 and current_io.get("output_field") != schema.outputs[0].get("name"):
            return True

        return False

    def _detect_schema_changes(self, mapping: ComponentMapping, schema: ComponentSchema) -> Dict[str, Any]:
        """Detect specific changes in component schema."""
        changes = {}

        if not mapping.io_mapping:
            return {"reason": "No existing I/O mapping"}

        current_io = mapping.io_mapping

        if current_io.get("input_types") != schema.input_types:
            changes["input_types"] = {
                "old": current_io.get("input_types"),
                "new": schema.input_types,
            }

        if current_io.get("output_types") != schema.output_types:
            changes["output_types"] = {
                "old": current_io.get("output_types"),
                "new": schema.output_types,
            }

        return changes

    def _create_io_mapping_from_schema(self, schema: ComponentSchema) -> Dict[str, Any]:
        """Create I/O mapping dictionary from component schema."""
        return {
            "component": schema.name,
            "class_name": schema.class_name,
            "module_path": schema.module_path,
            "input_field": schema.inputs[0]["name"] if schema.inputs else None,
            "output_field": schema.outputs[0]["name"] if schema.outputs else None,
            "input_types": schema.input_types,
            "output_types": schema.output_types,
            "inputs": schema.inputs,
            "outputs": schema.outputs,
        }

    def _extract_default_config(self, schema: ComponentSchema) -> Dict[str, Any]:
        """Extract default configuration from component schema."""
        config = {}

        # Extract default values from inputs
        for input_info in schema.inputs:
            if "default" in input_info:
                config[input_info["name"]] = input_info["default"]

        return config

    def _extract_adapter_config(self, schema: ComponentSchema) -> Dict[str, Any]:
        """Extract adapter configuration for runtime mapping."""
        return {
            "component_class": schema.class_name,
            "module_path": schema.module_path,
            "base_classes": schema.base_classes,
        }

    def _generate_discovery_statistics(
        self,
        all_schemas: Dict[str, ComponentSchema],
        existing_mappings: List[ComponentMapping],
    ) -> Dict[str, Any]:
        """Generate statistics from discovery process."""
        mapped_components = set()
        for mapping in existing_mappings:
            if mapping.io_mapping and mapping.io_mapping.get("component"):
                mapped_components.add(mapping.io_mapping["component"])

        category_counts = {}
        for schema in all_schemas.values():
            category = self._determine_component_category(schema)
            category_counts[category.value] = category_counts.get(category.value, 0) + 1

        return {
            "total_langflow_components": len(all_schemas),
            "mapped_components": len(mapped_components),
            "unmapped_components": len(all_schemas) - len(mapped_components),
            "mapping_coverage": len(mapped_components) / len(all_schemas) * 100 if all_schemas else 0,
            "components_by_category": category_counts,
        }

    def _generate_mapping_recommendations(self, new_components: List[Dict]) -> List[Dict[str, Any]]:
        """Generate prioritized mapping recommendations."""
        recommendations = []

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_components = sorted(
            new_components,
            key=lambda x: priority_order.get(x["recommendation"]["priority"], 3)
        )

        for component_info in sorted_components[:10]:  # Top 10 recommendations
            recommendations.append({
                "component_name": component_info["component_name"],
                "suggested_genesis_type": component_info["recommendation"]["suggested_genesis_type"],
                "category": component_info["recommendation"]["category"],
                "priority": component_info["recommendation"]["priority"],
                "rationale": component_info["recommendation"]["rationale"],
            })

        return recommendations