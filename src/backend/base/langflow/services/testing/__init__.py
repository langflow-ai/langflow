"""
End-to-End Integration Testing Framework - Phase 4.

This package provides comprehensive testing capabilities for Genesis specifications
including integration testing, workflow validation, and system verification.
"""

from .integration_tester import IntegrationTester, TestResult, TestSuite
from .workflow_validator import WorkflowValidator, ValidationScenario
from .system_verifier import SystemVerifier, VerificationResult

__all__ = [
    "IntegrationTester",
    "TestResult",
    "TestSuite",
    "WorkflowValidator",
    "ValidationScenario",
    "SystemVerifier",
    "VerificationResult"
]

__version__ = "1.0.0"