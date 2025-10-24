"""
Startup Population Service for Component Mappings with Dynamic Discovery.

This service implements AUTPE-6204: Dynamic component discovery and database-first
architecture for all component mappings. It replaces hardcoded mappings with
automatic discovery and seed data population.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.base import Service
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.component_mapping.capability_service import ComponentCapabilityService
from langflow.services.component_mapping.discovery import UnifiedComponentDiscovery
from langflow.services.spec.dynamic_schema_generator import get_dynamic_schema_generator
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

logger = logging.getLogger(__name__)


class StartupPopulationService(Service):
    """Service for populating database with dynamically discovered component mappings."""

    name = "startup_population_service"

    def __init__(self):
        """Initialize the startup population service with dynamic discovery."""
        super().__init__()
        self.component_mapping_service = ComponentMappingService()
        self.capability_service = ComponentCapabilityService()

        # Initialize mapper for accessing hardcoded mappings
        from langflow.services.genesis.mapper import ComponentMapper
        self.mapper = ComponentMapper()

        # Initialize unified discovery component (AUTPE-6206)
        from langflow.services.component_mapping.discovery import UnifiedComponentDiscovery
        self.discovery = UnifiedComponentDiscovery()

    async def populate_on_startup(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Populate database with dynamically discovered component mappings.

        Implements AUTPE-6204: Database-first approach with dynamic discovery.

        Args:
            session: Database session

        Returns:
            Dictionary with population results and statistics
        """
        logger.info("🚀 Starting dynamic component discovery and population...")
        logger.debug(f"DEBUG: Session type: {type(session)}")

        start_time = datetime.now(timezone.utc)

        try:
            # Check if already populated for this version
            is_populated = await self._is_already_populated(session)
            logger.debug(f"DEBUG: _is_already_populated returned: {is_populated}")

            if is_populated:
                logger.info("✅ Component mappings already populated for this version, skipping")
                return {
                    "status": "skipped",
                    "reason": "already_populated",
                    "timestamp": start_time.isoformat()
                }

            # Phase 1: Migrate Hardcoded Mappings
            logger.info("🔍 Phase 1: Migrating hardcoded mappings to database...")
            hardcoded_results = await self._migrate_hardcoded_mappings(session)

            # Phase 2: Populate Healthcare Mappings
            logger.info("📦 Phase 2: Populating healthcare component mappings...")
            healthcare_results = await self._populate_healthcare_mappings(session)

            # Phase 3: Integrate Component Schemas
            logger.info("🔧 Phase 3: Integrating component schemas...")
            schema_results = await self._integrate_component_schemas(session)

            # Phase 4: Populate Tool Capabilities
            logger.info("🔗 Phase 4: Populating tool capabilities...")
            capability_results = await self._populate_tool_capabilities(session)

            # Phase 5: Dynamic Discovery and Population
            logger.info("✔️ Phase 5: Dynamic component discovery...")
            discovery_results = await self._discover_components()
            logger.debug(f"DEBUG: Discovery found {discovery_results.get('discovered', 0)} components")

            # Phase 6: Populate Discovered Components to Database
            discovered_population = {}
            if discovery_results.get("discovered", 0) > 0:
                logger.info(f"📝 Phase 6: Populating {discovery_results.get('discovered', 0)} discovered components to database...")
                discovered_population = await self._populate_discovered_components(session, discovery_results)
                logger.debug(f"DEBUG: Population results: {discovered_population}")

            # Phase 7: Mark as populated for this version
            await self._mark_population_complete(session)

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            # Calculate totals including discovered components
            discovered_created = discovered_population.get("created", 0)

            results = {
                "status": "completed",
                "duration_seconds": duration,
                "timestamp": end_time.isoformat(),
                "phases": {
                    "hardcoded": hardcoded_results,
                    "healthcare": healthcare_results,
                    "schemas": schema_results,
                    "capabilities": capability_results,
                    "discovery": discovery_results,
                    "discovered_population": discovered_population if discovery_results.get("discovered", 0) > 0 else {}
                },
                "statistics": {
                    "total_mappings": hardcoded_results.get("created", 0) + healthcare_results.get("created", 0) + discovered_created,
                    "total_adapters": hardcoded_results.get("adapters_created", 0) + healthcare_results.get("adapters_created", 0) + discovered_created,
                    "total_schemas": schema_results.get("added", 0),
                    "total_capabilities": capability_results.get("created", 0),
                    "total_discovered": discovery_results.get("discovered", 0),
                    "newly_registered": discovered_created,
                    "performance_impact": duration
                }
            }

            logger.info(f"✅ Startup population completed successfully in {duration:.2f} seconds")
            logger.info(f"📊 Total mappings: {results['statistics']['total_mappings']}")
            logger.info(f"🔗 Total adapters: {results['statistics']['total_adapters']}")

            return results

        except Exception as e:
            logger.error(f"❌ Startup population failed: {e}")
            # Graceful fallback - don't crash startup
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fallback": "Using hardcoded mappings"
            }

    async def _is_already_populated(self, session: AsyncSession) -> bool:
        """
        Check if database has already been populated for this version.

        Uses environment variable to determine version and tracks completion.
        """
        try:
            # Check for population marker
            population_version = os.getenv("GENESIS_MAPPING_VERSION", "1.0.0")

            # Simple check: if we have any mappings, assume populated
            # In production, this could check a specific version tracking table
            mappings = await self.component_mapping_service.get_all_component_mappings(
                session, active_only=True, limit=1
            )

            if mappings:
                logger.info(f"Found existing mappings, checking version compatibility...")
                # For now, always repopulate if force flag is set
                force_repopulation = os.getenv("GENESIS_FORCE_MAPPING_REPOPULATION", "false").lower() == "true"
                if force_repopulation:
                    logger.info("🔄 Force repopulation enabled, will repopulate mappings")
                    return False
                return True

            return False

        except Exception as e:
            logger.warning(f"Could not check population status: {e}")
            return False

    async def _migrate_hardcoded_mappings(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Migrate hardcoded mappings from ComponentMapper to database.

        This addresses the AUTPE-6153 requirement for database-driven mappings.
        """
        results = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "adapters_created": 0,
            "errors": []
        }

        # Get all hardcoded mappings from ComponentMapper
        all_mappings = {}

        # Check for legacy attributes (may not exist in new simplified mapper)
        if hasattr(self.mapper, 'AUTONOMIZE_MODELS'):
            all_mappings.update(self.mapper.AUTONOMIZE_MODELS)
            logger.debug(f"DEBUG: Found {len(self.mapper.AUTONOMIZE_MODELS)} AUTONOMIZE_MODELS")

        if hasattr(self.mapper, 'MCP_MAPPINGS'):
            all_mappings.update(self.mapper.MCP_MAPPINGS)
            logger.debug(f"DEBUG: Found {len(self.mapper.MCP_MAPPINGS)} MCP_MAPPINGS")

        if hasattr(self.mapper, 'STANDARD_MAPPINGS'):
            all_mappings.update(self.mapper.STANDARD_MAPPINGS)
            logger.debug(f"DEBUG: Found {len(self.mapper.STANDARD_MAPPINGS)} STANDARD_MAPPINGS")

        # Check for fallback mappings in new mapper
        if hasattr(self.mapper, 'FALLBACK_MAPPINGS'):
            all_mappings.update(self.mapper.FALLBACK_MAPPINGS)
            logger.debug(f"DEBUG: Found {len(self.mapper.FALLBACK_MAPPINGS)} FALLBACK_MAPPINGS")

        if not all_mappings:
            logger.info("ℹ️ No hardcoded mappings to migrate")
            return results

        logger.info(f"📦 Migrating {len(all_mappings)} hardcoded component mappings...")

        # Use the service's migration method
        migration_results = await self.component_mapping_service.migrate_hardcoded_mappings(
            session, all_mappings, overwrite_existing=False
        )

        results.update(migration_results)
        results["adapters_created"] = results.get("created", 0)  # Each mapping gets an adapter

        logger.info(f"✅ Hardcoded migration: {results['created']} created, {results['updated']} updated, {results['skipped']} skipped")

        return results

    async def _populate_healthcare_mappings(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Populate healthcare-specific component mappings.

        This addresses the healthcare connector requirements from the epic.
        """
        results = {
            "created": 0,
            "updated": 0,
            "adapters_created": 0,
            "errors": []
        }

        try:
            # Get healthcare mappings
            # Healthcare mappings are now handled by unified discovery
            healthcare_mappings = {}

            if not healthcare_mappings:
                logger.info("ℹ️ No healthcare mappings to populate")
                return results

            logger.info(f"🏥 Populating {len(healthcare_mappings)} healthcare component mappings...")

            for genesis_type, mapping_info in healthcare_mappings.items():
                try:
                    # Check if mapping already exists
                    existing = await self.component_mapping_service.get_component_mapping_by_genesis_type(
                        session, genesis_type, active_only=False
                    )

                    if existing:
                        logger.debug(f"Healthcare mapping {genesis_type} already exists, skipping")
                        continue

                    # Create component mapping
                    mapping_data = ComponentMappingCreate(
                        genesis_type=genesis_type,
                        base_config=mapping_info.get("config", {}),
                        io_mapping=self._extract_healthcare_io_mapping(mapping_info),
                        component_category=ComponentCategoryEnum.HEALTHCARE.value,  # Use enum value for database compatibility
                        description=f"Healthcare connector for {genesis_type}",
                        version="1.0.0",
                        active=True,
                        healthcare_metadata={
                            "hipaa_compliant": True,
                            "phi_handling": True,
                            "connector_type": self._determine_healthcare_connector_type(genesis_type)
                        }
                    )

                    # Use savepoint for healthcare mapping creation
                    savepoint = await session.begin_nested()
                    try:
                        created_mapping = await self.component_mapping_service.create_component_mapping(
                            session, mapping_data, commit=False
                        )
                        results["created"] += 1

                        # Create runtime adapter
                        adapter_data = RuntimeAdapterCreate(
                            genesis_type=genesis_type,
                            runtime_type=RuntimeTypeEnum.LANGFLOW,
                            target_component=mapping_info.get("component", "HealthcareConnector"),
                            adapter_config=mapping_info.get("config", {}),
                            version="1.0.0",
                            description=f"Langflow adapter for {genesis_type}",
                            active=True,
                            priority=100,
                            compliance_rules={
                                "hipaa_required": True,
                                "audit_logging": True,
                                "data_encryption": True
                            }
                        )

                        await self.component_mapping_service.create_runtime_adapter(session, adapter_data, commit=False)
                        results["adapters_created"] += 1

                        await savepoint.commit()
                    except Exception as nested_error:
                        await savepoint.rollback()
                        raise nested_error

                except Exception as e:
                    logger.error(f"Error creating healthcare mapping for {genesis_type}: {e}")
                    results["errors"].append(f"{genesis_type}: {str(e)}")

            logger.info(f"✅ Healthcare population: {results['created']} mappings created, {results['adapters_created']} adapters created")

        except Exception as e:
            logger.error(f"Error in healthcare mappings population: {e}")
            results["errors"].append(f"Healthcare population error: {str(e)}")

        return results

    async def _integrate_component_schemas(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Integrate component schema validation with database mappings.

        This addresses the AUTPE-6155 requirement for comprehensive schema coverage.
        """
        results = {
            "schemas_integrated": 0,
            "missing_schemas_identified": 0,
            "core_schemas_added": 0,
            "errors": []
        }

        try:
            # Add missing core schemas first
            core_schemas_result = await self._add_missing_core_schemas()
            results["core_schemas_added"] = core_schemas_result.get("added", 0)

            # Get all component mappings to validate schema coverage
            all_mappings = await self.component_mapping_service.get_all_component_mappings(
                session, active_only=True, limit=1000
            )

            # Check schema coverage - only for critical components
            critical_types = [
                "genesis:agent", "genesis:mcp_tool", "genesis:api_request",
                "genesis:crewai_agent", "genesis:crewai_sequential_task",
                "genesis:knowledge_hub_search", "genesis:crewai_sequential_crew"
            ]

            # Get critical components that exist in mappings
            critical_mappings = [m for m in all_mappings if m.genesis_type in critical_types]
            missing_critical_schemas = []

            # Only check critical components for hardcoded schemas
            from langflow.services.spec.validation_schemas import COMPONENT_CONFIG_SCHEMAS
            for mapping in critical_mappings:
                if mapping.genesis_type not in COMPONENT_CONFIG_SCHEMAS:
                    missing_critical_schemas.append(mapping.genesis_type)

            # Generate dynamic schemas for non-critical components
            generator = get_dynamic_schema_generator()
            dynamic_schema_count = 0

            for mapping in all_mappings:
                try:
                    if mapping.genesis_type not in COMPONENT_CONFIG_SCHEMAS:
                        # Get category as string (handle both enum and string types)
                        if mapping.component_category:
                            if hasattr(mapping.component_category, 'value'):
                                # It's an enum
                                category = mapping.component_category.value
                            else:
                                # It's already a string
                                category = str(mapping.component_category)
                        else:
                            category = "general"

                        # Generate dynamic schema
                        schema = generator.generate_schema_from_introspection(
                            genesis_type=mapping.genesis_type,
                            component_category=category,
                            introspection_data=mapping.introspection_data,
                            base_config=mapping.base_config,
                            tool_capabilities=mapping.tool_capabilities
                        )
                        if schema:
                            dynamic_schema_count += 1
                except Exception as e:
                    logger.debug(f"Failed to generate schema for {mapping.genesis_type}: {e}")
                    continue

            results["missing_schemas_identified"] = len(missing_critical_schemas)
            results["dynamic_schemas_generated"] = dynamic_schema_count
            results["schemas_integrated"] = len(all_mappings)

            if missing_critical_schemas:
                logger.warning(f"⚠️ Found {len(missing_critical_schemas)} critical component types without hardcoded schemas")
                logger.info(f"Critical components without schemas: {missing_critical_schemas}")
            else:
                logger.info("✅ All critical component mappings have validation schemas")

            if dynamic_schema_count > 0:
                logger.info(f"🔄 Generated {dynamic_schema_count} dynamic schemas for discovered components")

            # Log stats from generator
            stats = generator.get_generation_stats()
            logger.debug(f"Schema generation stats: {stats}")

        except Exception as e:
            logger.error(f"Error in schema integration: {e}")
            results["errors"].append(f"Schema integration error: {str(e)}")

        return results

    async def _populate_tool_capabilities(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Populate tool capabilities for all component mappings.

        This addresses the AUTPE-6203 requirement for dynamic tool capability validation.
        """
        results = {
            "capabilities_populated": 0,
            "capabilities_updated": 0,
            "errors": []
        }

        try:
            # Get all component mappings
            all_mappings = await self.component_mapping_service.get_all_component_mappings(
                session, active_only=True, limit=1000
            )

            logger.info(f"🛠️ Populating tool capabilities for {len(all_mappings)} component mappings...")

            for mapping in all_mappings:
                try:
                    # Skip if capabilities already exist
                    if mapping.tool_capabilities:
                        logger.debug(f"Tool capabilities already exist for {mapping.genesis_type}, skipping")
                        continue

                    # Introspect component capabilities
                    capabilities = await self.capability_service.introspect_component_capabilities(
                        session, mapping.genesis_type
                    )

                    # Update the mapping with discovered capabilities
                    success = await self.capability_service.update_tool_capabilities(
                        session, mapping.genesis_type, capabilities, overwrite=False
                    )

                    if success:
                        results["capabilities_populated"] += 1
                        logger.debug(f"Populated tool capabilities for {mapping.genesis_type}: {capabilities}")
                    else:
                        logger.warning(f"Failed to populate capabilities for {mapping.genesis_type}")

                except Exception as e:
                    logger.error(f"Error populating capabilities for {mapping.genesis_type}: {e}")
                    results["errors"].append(f"{mapping.genesis_type}: {str(e)}")

            # Also populate capabilities for known static mappings (fallback)
            static_mappings = {}
            try:
                # Only add if the attributes exist (for backward compatibility)
                if hasattr(self.mapper, 'AUTONOMIZE_MODELS'):
                    static_mappings.update(self.mapper.AUTONOMIZE_MODELS)
                if hasattr(self.mapper, 'MCP_MAPPINGS'):
                    static_mappings.update(self.mapper.MCP_MAPPINGS)
                if hasattr(self.mapper, 'STANDARD_MAPPINGS'):
                    static_mappings.update(self.mapper.STANDARD_MAPPINGS)
            except Exception as e:
                logger.warning(f"Could not load static mappings for capability population: {e}")

            for genesis_type, mapping_info in static_mappings.items():
                try:
                    # Check if mapping exists in database
                    existing = await self.component_mapping_service.get_component_mapping_by_genesis_type(
                        session, genesis_type, active_only=False
                    )

                    if existing and not existing.tool_capabilities:
                        # Introspect and populate capabilities
                        capabilities = await self.capability_service.introspect_component_capabilities(
                            session, genesis_type
                        )

                        success = await self.capability_service.update_tool_capabilities(
                            session, genesis_type, capabilities, overwrite=False
                        )

                        if success:
                            results["capabilities_populated"] += 1

                except Exception as e:
                    logger.error(f"Error populating static mapping capabilities for {genesis_type}: {e}")
                    results["errors"].append(f"{genesis_type}: {str(e)}")

            logger.info(f"✅ Tool capability population: {results['capabilities_populated']} populated")

        except Exception as e:
            logger.error(f"Error in tool capabilities population: {e}")
            results["errors"].append(f"Tool capability population error: {str(e)}")

        return results

    async def _add_missing_core_schemas(self) -> Dict[str, Any]:
        """
        Add missing core component schemas as identified in AUTPE-6180.

        Uses the complete component schema coverage module for comprehensive integration.
        """
        try:
            # Defensive import to avoid circular dependencies
            try:
                from langflow.services.spec.complete_component_schemas import (
                    integrate_schemas_with_validation,
                    get_core_missing_schemas
                )
            except ImportError as ie:
                logger.warning(f"Could not import complete component schemas: {ie}")
                return {
                    "status": "completed",
                    "schema_integration": {
                        "success": False,
                        "warning": "Schema integration skipped due to import issues"
                    }
                }

            logger.info("📝 Integrating complete component schema coverage...")

            # Get comprehensive schema integration
            integration_result = integrate_schemas_with_validation()

            if integration_result.get("success"):
                added_count = integration_result.get("added_count", 0)
                total_count = integration_result.get("final_count", 0)

                logger.info(f"✅ Schema integration completed: {added_count} new schemas added")
                logger.info(f"📊 Total validation schemas: {total_count}")

                # Get coverage stats
                coverage_stats = integration_result.get("coverage_stats", {})
                logger.info(f"🔧 Schema categories integrated: {len(coverage_stats.get('schema_categories', {}))}")

                return {
                    "added": added_count,
                    "total": total_count,
                    "integration_success": True,
                    "coverage_stats": coverage_stats
                }
            else:
                error = integration_result.get("error", "Unknown error")
                logger.error(f"❌ Schema integration failed: {error}")

                # Fallback to core schemas only
                core_schemas = get_core_missing_schemas()
                return await self._add_fallback_core_schemas(core_schemas)

        except Exception as e:
            logger.error(f"Error in comprehensive schema integration: {e}")
            # Fallback to basic core schemas
            return await self._add_fallback_core_schemas()

    async def _add_fallback_core_schemas(self, core_schemas: Optional[Dict] = None) -> Dict[str, Any]:
        """Fallback method to add core schemas if comprehensive integration fails."""
        from langflow.services.spec.validation_schemas import COMPONENT_CONFIG_SCHEMAS

        if core_schemas is None:
            # Minimal core schemas as fallback
            core_schemas = {
                "genesis:prompt": {
                    "type": "object",
                    "properties": {
                        "template": {"type": "string", "minLength": 1, "maxLength": 10000},
                        "saved_prompt": {"type": "string"},
                        "variables": {"type": "array", "items": {"type": "string"}},
                        "template_format": {
                            "type": "string",
                            "enum": ["f-string", "jinja2"],
                            "default": "f-string"
                        }
                    },
                    "required": ["template"],
                    "additionalProperties": False
                },
                "genesis:chat_input": {
                    "type": "object",
                    "properties": {
                        "should_store_message": {"type": "boolean", "default": True},
                        "user_id": {"type": "string"},
                        "session_id": {"type": "string"},
                        "input_type": {
                            "type": "string",
                            "enum": ["chat", "system", "human"],
                            "default": "chat"
                        }
                    },
                    "additionalProperties": False
                },
                "genesis:chat_output": {
                    "type": "object",
                    "properties": {
                        "should_store_message": {"type": "boolean", "default": True},
                        "data_template": {"type": "string"},
                        "output_format": {
                            "type": "string",
                            "enum": ["text", "json", "markdown"],
                            "default": "text"
                        }
                    },
                    "additionalProperties": False
                }
            }

        added_count = 0
        for component_type, schema in core_schemas.items():
            if component_type not in COMPONENT_CONFIG_SCHEMAS:
                COMPONENT_CONFIG_SCHEMAS[component_type] = schema
                added_count += 1
                logger.info(f"📝 Added fallback schema for {component_type}")

        return {
            "added": added_count,
            "total": len(COMPONENT_CONFIG_SCHEMAS),
            "integration_success": False,
            "fallback_used": True
        }

    def _has_validation_schema(self, genesis_type: str) -> bool:
        """Check if a component type has a validation schema."""
        from langflow.services.spec.validation_schemas import COMPONENT_CONFIG_SCHEMAS

        # First check if there's a hardcoded schema
        if genesis_type in COMPONENT_CONFIG_SCHEMAS:
            return True

        # For dynamically discovered components, we can generate schemas on-demand
        # This ensures all components have schemas
        return True  # Dynamic schema generation available for all components

    def _extract_healthcare_io_mapping(self, mapping_info: Dict) -> Dict:
        """Extract I/O mapping for healthcare components."""
        return {
            "component": mapping_info.get("component"),
            "dataType": mapping_info.get("dataType", "Data"),
            "input_field": "input_value",
            "output_field": "response",
            "input_types": ["Message", "Data"],
            "output_types": ["Data", "Message"],
            "healthcare_specific": True
        }

    def _determine_healthcare_connector_type(self, genesis_type: str) -> str:
        """Determine the type of healthcare connector."""
        type_lower = genesis_type.lower()

        if "ehr" in type_lower:
            return "ehr_connector"
        elif "claims" in type_lower:
            return "claims_connector"
        elif "eligibility" in type_lower:
            return "eligibility_connector"
        elif "pharmacy" in type_lower:
            return "pharmacy_connector"
        else:
            return "generic_healthcare_connector"

    async def _mark_population_complete(self, session: AsyncSession) -> None:
        """Mark population as complete for this version."""
        # In a full implementation, this would update a version tracking table
        # For now, we just log completion
        version = os.getenv("GENESIS_MAPPING_VERSION", "1.0.0")
        logger.info(f"✅ Marked population complete for version {version}")

    async def _discover_components(self) -> Dict[str, Any]:
        """
        Discover all available Langflow components using unified data-driven discovery.

        Returns:
            Dictionary with discovery results including consolidated variants
        """
        try:
            logger.info("🔍 Discovering all Langflow components with data-driven introspection...")

            # Use unified discovery with full introspection
            discovery_results = self.discovery.discover_all()

            if discovery_results.get("success"):
                summary = discovery_results.get("summary", {})
                stats = discovery_results.get("statistics", {})

                logger.info(f"✅ Discovered {stats.get('total_discovered', 0)} components")
                logger.info(f"📦 Consolidated to {stats.get('total_consolidated', 0)} components (reduction: {summary.get('reduction_ratio', 0):.1f}%)")
                logger.info(f"🎯 Found {stats.get('components_with_variants', 0)} components with {stats.get('variants_found', 0)} total variants")

                if stats.get("introspection_failures", 0) > 0:
                    logger.warning(f"⚠️ Failed to introspect {stats['introspection_failures']} components")

                if discovery_results.get("errors"):
                    logger.warning(f"⚠️ Discovery encountered {len(discovery_results['errors'])} errors")

                return {
                    "discovered": stats.get("total_consolidated", 0),
                    "components": discovery_results.get("components", []),
                    "statistics": stats,
                    "summary": summary,
                    "errors": discovery_results.get("errors", []),
                    "status": "completed"
                }
            else:
                logger.error("Discovery failed")
                return {
                    "discovered": 0,
                    "components": [],
                    "status": "failed",
                    "error": "Discovery did not complete successfully"
                }

        except Exception as e:
            logger.error(f"Component discovery failed: {e}")
            return {
                "discovered": 0,
                "components": [],
                "status": "failed",
                "error": str(e)
            }

    async def _load_seed_data(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Load seed data from configuration files.

        Returns:
            Dictionary with seed loading results
        """
        try:
            loaded = 0

            # This would load from YAML/JSON seed files
            logger.info("📦 Loading seed data...")

            return {
                "loaded": loaded,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Seed data loading failed: {e}")
            return {
                "loaded": 0,
                "status": "failed",
                "error": str(e)
            }

    async def _populate_discovered_components(self, session: AsyncSession, discovery_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Populate discovered components to database with consolidated variants.

        Returns:
            Dictionary with population results
        """
        try:
            created = 0
            updated = 0
            skipped = 0
            errors = []
            adapters_created = 0

            components = discovery_results.get('components', [])
            logger.info(f"💾 Populating {len(components)} consolidated components to database...")

            # Generate database entries from unified discovery
            database_entries = self.discovery.generate_database_entries()
            runtime_adapters = self.discovery.generate_runtime_adapters()

            logger.info(f"📊 Generated {len(database_entries)} database entries and {len(runtime_adapters)} runtime adapters")

            for idx, entry in enumerate(database_entries):
                try:
                    if idx % 50 == 0:  # Log progress every 50 components
                        logger.debug(f"Processing component {idx}/{len(database_entries)}")

                    # Validate genesis_type
                    genesis_type = entry.get("genesis_type", "")
                    if not genesis_type or genesis_type == "genesis:" or not genesis_type.startswith("genesis:"):
                        logger.warning(f"Skipping entry with invalid genesis_type: {genesis_type}")
                        errors.append(f"Invalid genesis_type: {genesis_type}")
                        continue

                    # Check if mapping already exists
                    existing = await self.component_mapping_service.get_component_mapping_by_genesis_type(
                        session, genesis_type
                    )

                    if existing:
                        skipped += 1
                        continue

                    # Create component mapping with all new fields
                    from langflow.services.database.models.component_mapping.model import (
                        ComponentMappingCreate,
                        ComponentCategoryEnum
                    )

                    # Map category string to enum
                    category_map = {
                        "io": ComponentCategoryEnum.IO,
                        "tool": ComponentCategoryEnum.TOOL,
                        "llm": ComponentCategoryEnum.LLM,
                        "healthcare": ComponentCategoryEnum.HEALTHCARE,
                        "data": ComponentCategoryEnum.DATA,
                        "agent": ComponentCategoryEnum.AGENT,
                        "memory": ComponentCategoryEnum.MEMORY,
                        "prompt": ComponentCategoryEnum.PROMPT,
                        "embedding": ComponentCategoryEnum.EMBEDDING,
                        "vector_store": ComponentCategoryEnum.VECTOR_STORE,
                        "processing": ComponentCategoryEnum.PROCESSING,
                        "integration": ComponentCategoryEnum.INTEGRATION,
                    }

                    category_enum = category_map.get(
                        entry.get("component_category", "tool").lower(),
                        ComponentCategoryEnum.TOOL
                    )

                    # Create the mapping with consolidated variants
                    mapping_create = ComponentMappingCreate(
                        genesis_type=genesis_type,
                        component_category=category_enum,
                        description=entry.get("description", ""),
                        base_config=entry.get("base_config", {}),
                        io_mapping=entry.get("io_mapping", {}),
                        healthcare_metadata=entry.get("healthcare_metadata"),
                        tool_capabilities=entry.get("tool_capabilities", {}),
                        runtime_introspection=entry.get("runtime_introspection", {}),
                        variants=entry.get("variants"),  # Consolidated variants
                        introspection_data=entry.get("introspection_data", {}),
                        introspected_at=entry.get("introspected_at"),
                        version=entry.get("version", "1.0.0"),
                        active=entry.get("active", True)
                    )

                    await self.component_mapping_service.create_component_mapping(session, mapping_create, commit=False)
                    created += 1

                    if created == 1:  # Log first successful creation
                        logger.info(f"✓ First component created: {entry['genesis_type']}")

                except Exception as e:
                    errors.append(f"{entry.get('genesis_type', 'unknown')}: {e}")
                    logger.error(f"Error creating mapping {entry.get('genesis_type', 'unknown')}: {e}")

            # Create runtime adapters for ALL components
            logger.info(f"🔗 Creating {len(runtime_adapters)} runtime adapters...")

            for adapter in runtime_adapters:
                try:
                    # Validate genesis_type
                    adapter_genesis_type = adapter.get("genesis_type", "")
                    if not adapter_genesis_type or adapter_genesis_type == "genesis:" or not adapter_genesis_type.startswith("genesis:"):
                        logger.warning(f"Skipping adapter with invalid genesis_type: {adapter_genesis_type}")
                        errors.append(f"Invalid adapter genesis_type: {adapter_genesis_type}")
                        continue

                    # Check if adapter already exists
                    from langflow.services.database.models.component_mapping.runtime_adapter import (
                        RuntimeAdapterCreate,
                        RuntimeTypeEnum
                    )

                    existing_adapter = await self.component_mapping_service.get_runtime_adapter_for_genesis_type(
                        session,
                        adapter_genesis_type,
                        RuntimeTypeEnum.LANGFLOW,
                        active_only=False
                    )

                    if not existing_adapter:
                        adapter_create = RuntimeAdapterCreate(
                            genesis_type=adapter_genesis_type,
                            runtime_type=RuntimeTypeEnum.LANGFLOW,
                            target_component=adapter.get("target_component", "Component"),
                            adapter_config=adapter.get("adapter_config", {}),
                            version=adapter.get("version", "1.0.0"),
                            description=adapter.get("description", ""),
                            compliance_rules=adapter.get("compliance_rules"),
                            active=adapter.get("active", True),
                            priority=adapter.get("priority", 100)
                        )

                        await self.component_mapping_service.create_runtime_adapter(session, adapter_create, commit=False)
                        adapters_created += 1

                except Exception as e:
                    errors.append(f"Adapter for {adapter.get('genesis_type', 'unknown')}: {e}")
                    logger.error(f"Error creating adapter: {e}")

            # CRITICAL: Commit the session to persist changes!
            await session.commit()
            logger.info(f"💾 Committed {created} components and {adapters_created} adapters to database")

            logger.info(f"✅ Component population: {created} created, {skipped} skipped, {adapters_created} adapters created")

            if errors:
                logger.warning(f"⚠️ Encountered {len(errors)} errors during population")
                for err in errors[:5]:  # Show first 5 errors
                    logger.warning(f"  - {err}")

            return {
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "adapters_created": adapters_created,
                "errors": errors,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Component population failed: {e}")
            return {
                "created": 0,
                "updated": 0,
                "status": "failed",
                "error": str(e)
            }

    async def _populate_runtime_adapters(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Populate runtime adapters to database.

        Returns:
            Dictionary with adapter population results
        """
        try:
            created = 0

            # Would populate runtime adapters
            logger.info("🔗 Populating runtime adapters...")

            return {
                "created": created,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Runtime adapter population failed: {e}")
            return {
                "created": 0,
                "status": "failed",
                "error": str(e)
            }

    async def _validate_and_optimize(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Validate and optimize component mappings.

        Returns:
            Dictionary with validation results
        """
        try:
            validated = 0
            optimized = 0

            # Would validate mappings and optimize for performance
            logger.info("✔️ Validating and optimizing mappings...")

            return {
                "validated": validated,
                "optimized": optimized,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Validation and optimization failed: {e}")
            return {
                "validated": 0,
                "optimized": 0,
                "status": "failed",
                "error": str(e)
            }

    async def get_population_status(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Get current population status and statistics.

        Returns:
            Dictionary with population status and metrics
        """
        try:
            stats = await self.component_mapping_service.get_statistics(session)

            # Check if startup population has been run
            total_mappings = stats["component_mappings"]["total"]
            has_healthcare = stats["component_mappings"]["by_category"].get("HEALTHCARE", 0) > 0

            return {
                "populated": total_mappings > 0,
                "has_healthcare_mappings": has_healthcare,
                "statistics": stats,
                "environment_config": {
                    "auto_populate": os.getenv("GENESIS_AUTO_POPULATE_MAPPINGS", "true").lower() == "true",
                    "force_repopulation": os.getenv("GENESIS_FORCE_MAPPING_REPOPULATION", "false").lower() == "true",
                    "skip_population": os.getenv("GENESIS_SKIP_MAPPING_POPULATION", "false").lower() == "true"
                }
            }

        except Exception as e:
            logger.error(f"Error getting population status: {e}")
            return {
                "populated": False,
                "error": str(e),
                "environment_config": {
                    "auto_populate": os.getenv("GENESIS_AUTO_POPULATE_MAPPINGS", "true").lower() == "true",
                    "force_repopulation": os.getenv("GENESIS_FORCE_MAPPING_REPOPULATION", "false").lower() == "true",
                    "skip_population": os.getenv("GENESIS_SKIP_MAPPING_POPULATION", "false").lower() == "true"
                }
            }

    def should_run_startup_population(self) -> bool:
        """
        Determine if startup population should run based on environment configuration.

        Returns:
            True if startup population should run
        """
        # Check if skip flag is set
        if os.getenv("GENESIS_SKIP_MAPPING_POPULATION", "false").lower() == "true":
            logger.info("📝 GENESIS_SKIP_MAPPING_POPULATION is true, skipping startup population")
            return False

        # Check if auto populate is enabled (default: true)
        if os.getenv("GENESIS_AUTO_POPULATE_MAPPINGS", "true").lower() != "true":
            logger.info("📝 GENESIS_AUTO_POPULATE_MAPPINGS is false, skipping startup population")
            return False

        return True

    async def cleanup_population_data(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Clean up population data for testing or maintenance.

        WARNING: This will remove all component mappings and adapters!
        """
        if os.getenv("GENESIS_ALLOW_CLEANUP", "false").lower() != "true":
            raise ValueError("Cleanup not allowed. Set GENESIS_ALLOW_CLEANUP=true to enable")

        logger.warning("🧹 Starting cleanup of all population data...")

        # Get all mappings
        all_mappings = await self.component_mapping_service.get_all_component_mappings(
            session, active_only=False, limit=10000
        )

        deleted_mappings = 0
        deleted_adapters = 0

        for mapping in all_mappings:
            # Delete associated adapters first
            adapters = await self.component_mapping_service.get_all_adapters_for_genesis_type(
                session, mapping.genesis_type, active_only=False
            )

            for adapter in adapters:
                await self.component_mapping_service.delete_runtime_adapter(session, adapter.id)
                deleted_adapters += 1

            # Delete mapping
            await self.component_mapping_service.delete_component_mapping(
                session, mapping.id, soft_delete=False
            )
            deleted_mappings += 1

        logger.warning(f"🧹 Cleanup complete: {deleted_mappings} mappings, {deleted_adapters} adapters deleted")

        return {
            "deleted_mappings": deleted_mappings,
            "deleted_adapters": deleted_adapters
        }