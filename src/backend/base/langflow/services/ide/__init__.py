"""
IDE Integration Package for Genesis Specification Development - Phase 4.

This package provides comprehensive IDE integration including:
- Language Server Protocol (LSP) support for real-time validation
- Auto-completion for Genesis specification syntax
- Inline error reporting and suggestions
- Integration with VS Code and other LSP-compatible editors
"""

from .language_server import GenesisLanguageServer, start_language_server
from .lsp_client import GenesisLSPClient
from .vscode_extension import VSCodeExtensionGenerator

__all__ = [
    "GenesisLanguageServer",
    "start_language_server",
    "GenesisLSPClient",
    "VSCodeExtensionGenerator"
]

__version__ = "1.0.0"