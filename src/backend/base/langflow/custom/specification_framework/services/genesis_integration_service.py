"""
Professional Genesis Integration Service for the Dynamic Agent Specification Framework.

This service provides seamless integration between the new professional framework
and the existing Genesis specification services while maintaining backward compatibility
and professional naming conventions.
"""

import logging
from typing import Dict, Any, Optional, Type, TYPE_CHECKING
from datetime import datetime

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from ..core.specification_processor import SpecificationProcessor

from ..models.processing_context import ProcessingContext

# Legacy Genesis imports (will be replaced gradually)
try:
    from langflow.services.spec import SpecService
    from langflow.services.runtime import LangflowConverter
except ImportError:
    # Fallback if Genesis services are not available
    SpecService = None
    LangflowConverter = None

logger = logging.getLogger(__name__)


class GenesisIntegrationService:
    """
    Professional service for integrating with existing Genesis infrastructure.

    This service provides:
    - Seamless integration with existing SpecService
    - Professional wrapper around legacy components
    - Gradual migration path from old to new architecture
    - Backward compatibility for existing API endpoints
    - Enhanced error handling and logging
    - Performance monitoring and optimization
    """

    def __init__(self,
                 spec_service: Optional[Type] = None,
                 langflow_converter: Optional[Type] = None,
                 specification_processor: Optional["SpecificationProcessor"] = None):
        """
        Initialize the Genesis integration service.

        Args:
            spec_service: Legacy SpecService (optional)
            langflow_converter: Legacy LangflowConverter (optional)
            specification_processor: Professional framework processor (optional, will be lazily loaded)
        """
        self.spec_service = spec_service or SpecService
        self.langflow_converter_class = langflow_converter or LangflowConverter

        # Use dependency injection to avoid circular imports
        self._specification_processor = specification_processor

        # Track integration metrics
        self.integration_metrics = {
            "legacy_calls": 0,
            "framework_calls": 0,
            "fallback_calls": 0,
            "error_count": 0,
            "last_reset": datetime.utcnow()
        }

    @property
    def specification_processor(self) -> "SpecificationProcessor":
        """
        Lazy load the SpecificationProcessor to avoid circular imports.

        Returns:
            SpecificationProcessor instance
        """
        if self._specification_processor is None:
            # Import here to avoid circular import
            from ..core.specification_processor import SpecificationProcessor
            self._specification_processor = SpecificationProcessor()
        return self._specification_processor

    async def convert_specification_to_workflow(self,
                                              specification: Dict[str, Any],
                                              variables: Optional[Dict[str, Any]] = None,
                                              use_legacy_fallback: bool = False,
                                              enable_healthcare_compliance: bool = False,
                                              enable_performance_benchmarking: bool = False) -> Dict[str, Any]:
        """
        Convert agent specification to Langflow workflow using the new framework.

        This is the main integration method that provides a professional interface
        while maintaining compatibility with existing Genesis APIs.

        Args:
            specification: Agent specification dictionary
            variables: Optional variables for template substitution
            use_legacy_fallback: Whether to use legacy services as fallback
            enable_healthcare_compliance: Enable HIPAA compliance validation
            enable_performance_benchmarking: Enable detailed performance metrics

        Returns:
            Dictionary containing conversion result and metadata
        """
        conversion_start = datetime.utcnow()

        try:
            logger.info("Starting specification to workflow conversion using professional framework")

            # Use the new professional framework
            processing_result = await self.specification_processor.process_specification(
                specification,
                variables=variables,
                enable_healthcare_compliance=enable_healthcare_compliance,
                enable_performance_benchmarking=enable_performance_benchmarking
            )

            self.integration_metrics["framework_calls"] += 1

            if processing_result.success:
                logger.info(f"Professional framework conversion successful in {processing_result.processing_time_seconds:.3f}s")

                return {
                    "success": True,
                    "flow": processing_result.workflow,
                    "metadata": {
                        "conversion_method": "professional_framework",
                        "processing_time_seconds": processing_result.processing_time_seconds,
                        "component_count": processing_result.component_count,
                        "edge_count": processing_result.edge_count,
                        "automation_metrics": processing_result.automation_metrics,
                        "performance_metrics": processing_result.performance_metrics,
                        "compliance_metrics": processing_result.compliance_metrics,
                        "spec_validation": processing_result.spec_validation.to_dict() if processing_result.spec_validation else None,
                        "workflow_validation": processing_result.workflow_validation.to_dict() if processing_result.workflow_validation else None
                    },
                    "errors": [],
                    "warnings": []
                }

            else:
                logger.warning("Professional framework conversion failed, attempting legacy fallback")

                if use_legacy_fallback:
                    return await self._try_legacy_conversion(specification, variables, conversion_start)
                else:
                    return {
                        "success": False,
                        "flow": None,
                        "metadata": {
                            "conversion_method": "professional_framework",
                            "error": processing_result.error_message
                        },
                        "errors": [processing_result.error_message] if processing_result.error_message else [],
                        "warnings": []
                    }

        except Exception as e:
            self.integration_metrics["error_count"] += 1
            error_message = f"Professional framework conversion failed: {str(e)}"
            logger.error(error_message, exc_info=True)

            if use_legacy_fallback:
                logger.info("Attempting legacy fallback due to framework error")
                return await self._try_legacy_conversion(specification, variables, conversion_start)
            else:
                return {
                    "success": False,
                    "flow": None,
                    "metadata": {
                        "conversion_method": "professional_framework",
                        "error": error_message,
                        "conversion_time_seconds": (datetime.utcnow() - conversion_start).total_seconds()
                    },
                    "errors": [error_message],
                    "warnings": []
                }

    async def validate_specification_only(self,
                                        specification: Dict[str, Any],
                                        enable_healthcare_compliance: bool = False) -> Dict[str, Any]:
        """
        Validate specification without converting to workflow.

        Args:
            specification: Agent specification to validate
            enable_healthcare_compliance: Enable healthcare compliance validation

        Returns:
            Dictionary containing validation results
        """
        try:
            logger.debug("Validating specification using professional framework")

            validation_result = await self.specification_processor.validate_specification_only(
                specification,
                healthcare_compliance=enable_healthcare_compliance
            )

            return {
                "valid": validation_result["valid"],
                "errors": validation_result["errors"],
                "warnings": validation_result["warnings"],
                "healthcare_compliant": validation_result.get("healthcare_compliant"),
                "validation_method": "professional_framework"
            }

        except Exception as e:
            error_message = f"Specification validation failed: {str(e)}"
            logger.error(error_message, exc_info=True)

            return {
                "valid": False,
                "errors": [error_message],
                "warnings": [],
                "healthcare_compliant": False if enable_healthcare_compliance else None,
                "validation_method": "professional_framework"
            }

    async def get_component_mappings(self,
                                   specification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get component mappings for a specification.

        Args:
            specification: Agent specification

        Returns:
            Dictionary containing component mappings
        """
        try:
            logger.debug("Getting component mappings using professional framework")

            # Use the professional framework's component discovery
            component_discovery = self.specification_processor.component_discovery
            component_mappings = await component_discovery.discover_components(
                specification,
                ProcessingContext(specification=specification)
            )

            return {
                "success": True,
                "mappings": {k: v.to_dict() for k, v in component_mappings.items()},
                "mapping_method": "professional_framework"
            }

        except Exception as e:
            error_message = f"Component mapping discovery failed: {str(e)}"
            logger.error(error_message, exc_info=True)

            return {
                "success": False,
                "mappings": {},
                "error": error_message,
                "mapping_method": "professional_framework"
            }

    async def get_integration_metrics(self) -> Dict[str, Any]:
        """
        Get integration service metrics.

        Returns:
            Dictionary containing integration metrics
        """
        current_time = datetime.utcnow()
        uptime_seconds = (current_time - self.integration_metrics["last_reset"]).total_seconds()

        return {
            "uptime_seconds": uptime_seconds,
            "legacy_calls": self.integration_metrics["legacy_calls"],
            "framework_calls": self.integration_metrics["framework_calls"],
            "fallback_calls": self.integration_metrics["fallback_calls"],
            "error_count": self.integration_metrics["error_count"],
            "total_calls": (
                self.integration_metrics["legacy_calls"] +
                self.integration_metrics["framework_calls"] +
                self.integration_metrics["fallback_calls"]
            ),
            "framework_usage_percentage": self._calculate_framework_usage_percentage(),
            "error_rate": self._calculate_error_rate(),
            "last_reset": self.integration_metrics["last_reset"].isoformat()
        }

    def reset_integration_metrics(self) -> None:
        """Reset integration metrics."""
        self.integration_metrics = {
            "legacy_calls": 0,
            "framework_calls": 0,
            "fallback_calls": 0,
            "error_count": 0,
            "last_reset": datetime.utcnow()
        }
        logger.info("Integration metrics reset")

    async def migrate_to_professional_framework(self,
                                              specification: Dict[str, Any],
                                              test_conversion: bool = True) -> Dict[str, Any]:
        """
        Test migration of a specification to the professional framework.

        Args:
            specification: Specification to test migration for
            test_conversion: Whether to test full conversion

        Returns:
            Dictionary containing migration assessment
        """
        try:
            logger.info("Testing specification migration to professional framework")

            migration_result = {
                "compatible": False,
                "issues": [],
                "recommendations": [],
                "conversion_test": None
            }

            # Phase 1: Validation test
            validation_result = await self.validate_specification_only(specification)
            if not validation_result["valid"]:
                migration_result["issues"].extend(validation_result["errors"])
                migration_result["recommendations"].append("Fix validation errors before migration")
            else:
                migration_result["compatible"] = True

            # Phase 2: Conversion test (if requested and validation passed)
            if test_conversion and migration_result["compatible"]:
                conversion_result = await self.convert_specification_to_workflow(
                    specification,
                    use_legacy_fallback=False
                )

                migration_result["conversion_test"] = {
                    "success": conversion_result["success"],
                    "metadata": conversion_result.get("metadata", {}),
                    "errors": conversion_result.get("errors", []),
                    "warnings": conversion_result.get("warnings", [])
                }

                if not conversion_result["success"]:
                    migration_result["compatible"] = False
                    migration_result["issues"].extend(conversion_result["errors"])

            # Phase 3: Generate recommendations
            if migration_result["compatible"]:
                migration_result["recommendations"].extend([
                    "Specification is compatible with professional framework",
                    "Consider enabling healthcare compliance if applicable",
                    "Test thoroughly in development environment before production use"
                ])
            else:
                migration_result["recommendations"].extend([
                    "Address validation and conversion issues",
                    "Consider gradual migration approach",
                    "Use legacy fallback during transition period"
                ])

            return migration_result

        except Exception as e:
            error_message = f"Migration assessment failed: {str(e)}"
            logger.error(error_message, exc_info=True)

            return {
                "compatible": False,
                "issues": [error_message],
                "recommendations": ["Fix migration assessment errors before proceeding"],
                "conversion_test": None
            }

    async def _try_legacy_conversion(self,
                                   specification: Dict[str, Any],
                                   variables: Optional[Dict[str, Any]] = None,
                                   conversion_start: datetime = None) -> Dict[str, Any]:
        """
        Attempt conversion using legacy Genesis services.

        Args:
            specification: Agent specification
            variables: Template variables
            conversion_start: Conversion start time

        Returns:
            Dictionary containing legacy conversion result
        """
        if conversion_start is None:
            conversion_start = datetime.utcnow()

        try:
            self.integration_metrics["fallback_calls"] += 1
            logger.info("Attempting legacy Genesis conversion")

            # Check if legacy services are available
            if not self._legacy_services_available():
                return {
                    "success": False,
                    "flow": None,
                    "metadata": {
                        "conversion_method": "legacy_fallback",
                        "error": "Legacy services not available"
                    },
                    "errors": ["Legacy Genesis services not available"],
                    "warnings": []
                }

            # Use legacy LangflowConverter
            converter = self.langflow_converter_class()

            # Convert using legacy method
            if hasattr(converter, 'convert_to_langflow'):
                conversion_result = await converter.convert_to_langflow(specification, variables)
            else:
                # Fallback to older method name
                conversion_result = await converter.convert_to_runtime(specification, variables)

            conversion_time = (datetime.utcnow() - conversion_start).total_seconds()

            if conversion_result.success:
                logger.info(f"Legacy conversion successful in {conversion_time:.3f}s")

                return {
                    "success": True,
                    "flow": conversion_result.flow_data,
                    "metadata": {
                        "conversion_method": "legacy_fallback",
                        "conversion_time_seconds": conversion_time,
                        "performance_metrics": conversion_result.performance_metrics or {},
                        "legacy_metadata": conversion_result.metadata or {}
                    },
                    "errors": conversion_result.errors or [],
                    "warnings": ["Used legacy conversion as fallback"]
                }
            else:
                logger.error("Legacy conversion also failed")

                return {
                    "success": False,
                    "flow": None,
                    "metadata": {
                        "conversion_method": "legacy_fallback",
                        "conversion_time_seconds": conversion_time,
                        "error": "Both professional framework and legacy conversion failed"
                    },
                    "errors": conversion_result.errors or ["Legacy conversion failed"],
                    "warnings": []
                }

        except Exception as e:
            self.integration_metrics["error_count"] += 1
            error_message = f"Legacy conversion failed: {str(e)}"
            logger.error(error_message, exc_info=True)

            conversion_time = (datetime.utcnow() - conversion_start).total_seconds()

            return {
                "success": False,
                "flow": None,
                "metadata": {
                    "conversion_method": "legacy_fallback",
                    "conversion_time_seconds": conversion_time,
                    "error": error_message
                },
                "errors": [error_message],
                "warnings": []
            }

    def _legacy_services_available(self) -> bool:
        """Check if legacy Genesis services are available."""
        return all([
            self.spec_service is not None,
            self.langflow_converter_class is not None
        ])

    def _calculate_framework_usage_percentage(self) -> float:
        """Calculate percentage of calls using the professional framework."""
        total_calls = (
            self.integration_metrics["legacy_calls"] +
            self.integration_metrics["framework_calls"] +
            self.integration_metrics["fallback_calls"]
        )

        if total_calls == 0:
            return 0.0

        return (self.integration_metrics["framework_calls"] / total_calls) * 100

    def _calculate_error_rate(self) -> float:
        """Calculate error rate percentage."""
        total_calls = (
            self.integration_metrics["legacy_calls"] +
            self.integration_metrics["framework_calls"] +
            self.integration_metrics["fallback_calls"]
        )

        if total_calls == 0:
            return 0.0

        return (self.integration_metrics["error_count"] / total_calls) * 100

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on integration service.

        Returns:
            Dictionary containing health status
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {},
            "issues": []
        }

        try:
            # Check professional framework
            try:
                # Simple validation test
                test_spec = {
                    "name": "Health Check Test",
                    "description": "Test specification for health check",
                    "agentGoal": "Test agent goal",
                    "components": {
                        "test_component": {
                            "type": "genesis:agent",
                            "name": "Test Agent"
                        }
                    }
                }

                validation_result = await self.validate_specification_only(test_spec)
                health_status["components"]["professional_framework"] = {
                    "status": "healthy" if validation_result["valid"] else "degraded",
                    "details": "Validation test passed" if validation_result["valid"] else "Validation test failed"
                }

                if not validation_result["valid"]:
                    health_status["issues"].append("Professional framework validation issues")

            except Exception as e:
                health_status["components"]["professional_framework"] = {
                    "status": "unhealthy",
                    "details": f"Framework check failed: {str(e)}"
                }
                health_status["issues"].append("Professional framework unavailable")

            # Check legacy services
            if self._legacy_services_available():
                health_status["components"]["legacy_services"] = {
                    "status": "healthy",
                    "details": "Legacy services available"
                }
            else:
                health_status["components"]["legacy_services"] = {
                    "status": "unavailable",
                    "details": "Legacy services not available"
                }

            # Overall status
            if health_status["issues"]:
                if len(health_status["issues"]) > 1:
                    health_status["status"] = "unhealthy"
                else:
                    health_status["status"] = "degraded"

            # Add metrics
            health_status["metrics"] = await self.get_integration_metrics()

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["issues"].append(f"Health check failed: {str(e)}")

        return health_status