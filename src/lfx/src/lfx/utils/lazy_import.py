"""Lazy attribute importing for component packages -- the STABLE public home.

:func:`import_mod` powers the ``__getattr__``-based lazy ``__init__.py`` shape
used by ``lfx.components`` category packages AND by extracted bundle packages
(the ``lfx-bundles`` metapackage's provider folders and the graduated
``lfx-<provider>`` distributions).  Because separately-installed bundles import
it, this module is part of the BUNDLE_API surface: the symbol's name,
signature, and semantics are contract-stable (see BUNDLE_API.md).

``lfx.components._importing`` re-exports :func:`import_mod` for backward
compatibility with in-tree callers and any external code that used the old
internal path; new code -- and all bundle packages -- should import from here.
"""

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
        except ModuleNotFoundError:
            msg = f"module '{package!r}' has no attribute {attr_name!r}"
            raise AttributeError(msg) from None
    else:
        try:
            module = import_module(f".{module_name}", package=package)
        except ModuleNotFoundError as e:
            # Check if this is a missing dependency or a missing module
            if "No module named" in str(e) and package in str(e):
                # This is likely a missing module file, not a dependency issue
                msg = f"module '{package}.{module_name}' not found"
                raise ImportError(msg) from None
            # This is likely a missing dependency, let the original error bubble up
            raise
        result = getattr(module, attr_name)
    return result
