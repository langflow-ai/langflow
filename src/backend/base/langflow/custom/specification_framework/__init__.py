"""
Dynamic Agent Specification Framework

A comprehensive framework for converting YAML agent specifications to Langflow JSON workflows
with automatic component discovery, edge generation, and healthcare compliance validation.
"""

from .core.specification_processor import SpecificationProcessor
from .services.component_discovery import LangflowComponentValidator
from .services.workflow_converter import WorkflowConverter
from .services.connection_builder import ConnectionBuilder
from .services.genesis_integration_service import GenesisIntegrationService
from .validation.specification_validator import SpecificationValidator
from .validation.workflow_validator import WorkflowValidator
from .utils.variable_resolver import VariableResolver
from .utils.langflow_compatibility import LangflowCompatibilityHelper

__version__ = "2.0.0"
__all__ = [
    "SpecificationProcessor",
    "LangflowComponentValidator",
    "WorkflowConverter",
    "ConnectionBuilder",
    "GenesisIntegrationService",
    "SpecificationValidator",
    "WorkflowValidator",
    "VariableResolver",
    "LangflowCompatibilityHelper"
]