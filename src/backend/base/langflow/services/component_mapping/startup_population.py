"""
Startup Population Service for Component Mappings and Schema Integration.

This service implements the unified startup population system that combines
hardcoded component mapping migration, healthcare connector mappings, and
component schema validation integration as specified in AUTPE-6180.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.base import Service
from langflow.services.component_mapping.service import ComponentMappingService
from langflow.services.component_mapping.healthcare_mappings import get_healthcare_component_mappings
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
from langflow.custom.genesis.spec.mapper import ComponentMapper

logger = logging.getLogger(__name__)


class StartupPopulationService(Service):
    """Service for populating database with all component mappings and schemas on startup."""

    name = "startup_population_service"

    def __init__(self):
        """Initialize the startup population service."""
        super().__init__()
        self.component_mapping_service = ComponentMappingService()
        self.mapper = ComponentMapper()

    async def populate_on_startup(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Populate database with all component mappings and schemas on startup.

        This is the main entry point that coordinates all population activities
        as specified in AUTPE-6180.

        Args:
            session: Database session

        Returns:
            Dictionary with population results and statistics
        """
        logger.info("🚀 Starting unified startup population service...")

        start_time = datetime.now(timezone.utc)

        try:
            # Check if already populated for this version
            if await self._is_already_populated(session):
                logger.info("✅ Component mappings already populated for this version, skipping")
                return {
                    "status": "skipped",
                    "reason": "already_populated",
                    "timestamp": start_time.isoformat()
                }

            # Phase 1: Migrate hardcoded mappings
            logger.info("📦 Phase 1: Migrating hardcoded component mappings...")
            hardcoded_results = await self._migrate_hardcoded_mappings(session)

            # Phase 2: Populate healthcare mappings
            logger.info("🏥 Phase 2: Populating healthcare connector mappings...")
            healthcare_results = await self._populate_healthcare_mappings(session)

            # Phase 3: Integrate component schemas
            logger.info("🔧 Phase 3: Integrating component schema validation...")
            schema_results = await self._integrate_component_schemas(session)

            # Phase 4: Mark as populated for this version
            await self._mark_population_complete(session)

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            results = {
                "status": "completed",
                "duration_seconds": duration,
                "timestamp": end_time.isoformat(),
                "phases": {
                    "hardcoded_mappings": hardcoded_results,
                    "healthcare_mappings": healthcare_results,
                    "schema_integration": schema_results
                },
                "statistics": {
                    "total_mappings": (
                        hardcoded_results.get("created", 0) +
                        healthcare_results.get("created", 0)
                    ),
                    "total_adapters": (
                        hardcoded_results.get("adapters_created", 0) +
                        healthcare_results.get("adapters_created", 0)
                    ),
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
        all_mappings.update(self.mapper.AUTONOMIZE_MODELS)
        all_mappings.update(self.mapper.MCP_MAPPINGS)
        all_mappings.update(self.mapper.STANDARD_MAPPINGS)

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
            healthcare_mappings = get_healthcare_component_mappings()

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

                    created_mapping = await self.component_mapping_service.create_component_mapping(
                        session, mapping_data
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

                    await self.component_mapping_service.create_runtime_adapter(session, adapter_data)
                    results["adapters_created"] += 1

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

            # Check schema coverage
            missing_schemas = []
            for mapping in all_mappings:
                if not self._has_validation_schema(mapping.genesis_type):
                    missing_schemas.append(mapping.genesis_type)

            results["missing_schemas_identified"] = len(missing_schemas)
            results["schemas_integrated"] = len(all_mappings) - len(missing_schemas)

            if missing_schemas:
                logger.warning(f"⚠️ Found {len(missing_schemas)} component types without validation schemas")
                logger.info(f"Missing schemas for: {missing_schemas[:10]}{'...' if len(missing_schemas) > 10 else ''}")
            else:
                logger.info("✅ All component mappings have validation schemas")

        except Exception as e:
            logger.error(f"Error in schema integration: {e}")
            results["errors"].append(f"Schema integration error: {str(e)}")

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
                "genesis:prompt_template": {
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
        return genesis_type in COMPONENT_CONFIG_SCHEMAS

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