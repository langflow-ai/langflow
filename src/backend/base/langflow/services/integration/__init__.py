"""
Seamless Integration Module - Phase 4 Final Integration.

This package provides the unified integration layer that brings together all
Phase 1-3 components with Phase 4 enhancements to deliver an exceptional
Genesis specification development experience.
"""

from .unified_service import UnifiedGenesisService, GenesisConfig
from .workflow_orchestrator import WorkflowOrchestrator, WorkflowStep
from .experience_manager import ExperienceManager, DeveloperExperience

__all__ = [
    "UnifiedGenesisService",
    "GenesisConfig",
    "WorkflowOrchestrator",
    "WorkflowStep",
    "ExperienceManager",
    "DeveloperExperience"
]

__version__ = "1.0.0"