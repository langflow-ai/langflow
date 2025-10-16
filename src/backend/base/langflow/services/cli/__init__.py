"""
Enhanced CLI Package for Genesis Specification Development - Phase 4.

This package provides comprehensive CLI tools for Genesis specification development,
including real-time validation, interactive creation, performance monitoring, and
integration with all Phase 1-3 enhancements.
"""

from .enhanced_cli import EnhancedCLI, CLIConfig, create_enhanced_cli
from .commands import cli, spec_commands

__all__ = [
    "EnhancedCLI",
    "CLIConfig",
    "create_enhanced_cli",
    "cli",
    "spec_commands"
]

__version__ = "1.0.0"