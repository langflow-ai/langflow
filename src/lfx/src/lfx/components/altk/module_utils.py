"""Utility functions for module management in the policies component."""

import sys


def unload_module(name: str) -> None:
    """Remove a module and all its submodules from sys.modules.

    This ensures complete cleanup of dynamically generated modules,
    including any nested imports that may have been created.

    Args:
        name: The name of the module to unload
    """
    # Remove the main module
    if name in sys.modules:
        del sys.modules[name]

    # Remove all submodules (e.g., module.submodule)
    modules_to_remove = [mod_name for mod_name in sys.modules if mod_name.startswith(f"{name}.")]
    for mod_name in modules_to_remove:
        del sys.modules[mod_name]
