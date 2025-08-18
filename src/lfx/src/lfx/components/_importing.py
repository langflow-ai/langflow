"""Import utilities for LangFlow components."""

from __future__ import annotations

from importlib import import_module


def import_mod(
    attr_name: str,
    module_name: str | None,
    package: str | None,
) -> object:
    """Import an attribute from a module located in a package.

    This utility function is used in custom __getattr__ methods within __init__.py
    files to dynamically import attributes.

    Args:
        attr_name: The name of the attribute to import.
        module_name: The name of the module to import from. If None, the attribute
            is imported from the package itself.
        package: The name of the package where the module is located.
    """
    if module_name == "__module__" or module_name is None:
        try:
            result = import_module(f".{attr_name}", package=package)
        except ModuleNotFoundError as e:
            # Check if this is a missing dependency error vs missing module error
            if f"No module named '{package}.{attr_name}'" in str(e):
                # The target module itself doesn't exist
                msg = f"module '{package!r}' has no attribute {attr_name!r}"
                raise AttributeError(msg) from None
            # This is a dependency error within the module - re-raise as ImportError
            msg = f"Could not import module '{package}.{attr_name}': {e}"
            raise ImportError(msg) from e
    else:
        try:
            module = import_module(f".{module_name}", package=package)
        except ModuleNotFoundError as e:
            # Check if this is a missing dependency error vs missing module error
            if f"No module named '{package}.{module_name}'" in str(e):
                # The target module itself doesn't exist
                msg = f"module '{package!r}.{module_name!r}' not found"
                raise ImportError(msg) from None
            # This is a dependency error within the module - re-raise as ImportError
            msg = f"Could not import module '{package}.{module_name}': {e}"
            raise ImportError(msg) from e
        result = getattr(module, attr_name)
    return result
