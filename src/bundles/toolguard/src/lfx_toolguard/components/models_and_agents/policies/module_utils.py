"""Module-management helpers for the ToolGuard Policies extension."""

import sys
from pathlib import Path
from types import ModuleType


def ensure_toolguard_module_path_compat(runtime_module: ModuleType) -> None:
    """Backport Windows module-path handling for ToolGuard's in-memory loader.

    ToolGuard 0.2.21 converts forward slashes in generated ``FileTwin`` paths to
    Python module dots but leaves Windows backslashes untouched. Runtime methods
    resolve this module-global helper when guards are entered, so replacing it
    once is enough to make Windows-generated guards importable. The behavior
    probe leaves future fixed ToolGuard releases unchanged.
    """
    converter = getattr(runtime_module, "_file_to_module_name", None)
    if not callable(converter):
        return

    windows_probe = r"policies\guard.py"
    posix_probe = "policies/guard.py"
    try:
        windows_result = converter(windows_probe)
        posix_result = converter(posix_probe)
    except Exception:  # noqa: BLE001
        # This is a private third-party helper; an unsupported future contract
        # must not prevent ToolGuard itself from importing.
        return

    if (windows_result, posix_result) != (r"policies\guard", "policies.guard"):
        # Patch only the exact ToolGuard 0.2.21 behavior. Fixed and unknown
        # future implementations keep their own converter.
        return

    def file_to_module_name(file_path: str | Path) -> str:
        return str(file_path).removesuffix(".py").replace("\\", ".").replace("/", ".")

    runtime_module.__dict__["_file_to_module_name"] = file_to_module_name


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
