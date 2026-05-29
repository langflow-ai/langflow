from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    # These imports are only for type checking and match _dynamic_imports
    from lfx.components import (
        chains,
        custom_component,
        data,
        deactivated,
        documentloaders,
        embeddings,
        files_ingestion,
        helpers,
        homeassistant,
        huggingface,
        icosacomputing,
        input_output,
        langchain_utilities,
        link_extractors,
        logic,
        models_and_agents,
        output_parsers,
        processing,
        prototypes,
        textsplitters,
        toolkits,
        tools,
        vectorstores,
        yahoosearch,
    )


# Dynamic imports mapping - maps both modules and individual components
_dynamic_imports = {
    # Category modules (existing functionality)
    "chains": "__module__",
    "custom_component": "__module__",
    "data": "__module__",
    "deactivated": "__module__",
    "documentloaders": "__module__",
    "embeddings": "__module__",
    "files_ingestion": "__module__",
    "helpers": "__module__",
    "homeassistant": "__module__",
    "huggingface": "__module__",
    "icosacomputing": "__module__",
    "input_output": "__module__",
    "langchain_utilities": "__module__",
    "link_extractors": "__module__",
    "logic": "__module__",
    "models_and_agents": "__module__",
    "output_parsers": "__module__",
    "processing": "__module__",
    "prototypes": "__module__",
    "textsplitters": "__module__",
    "toolkits": "__module__",
    "tools": "__module__",
    "vectorstores": "__module__",
    "yahoosearch": "__module__",
}

# Track which modules we've already discovered to avoid re-scanning
_discovered_modules = set()


def _discover_components_from_module(module_name):
    """Discover individual components from a specific module on-demand."""
    if module_name in _discovered_modules or module_name == "notion":
        return

    try:
        # Try to import the module and get its dynamic imports
        module = import_mod(module_name, "__module__", __spec__.parent)

        if hasattr(module, "_dynamic_imports"):
            # Add each component from this module to our main mapping
            for comp_name, comp_file in module._dynamic_imports.items():
                # Create the full path: module_name.comp_file
                _dynamic_imports[comp_name] = f"{module_name}.{comp_file}"
                # Note: We don't add component names to __all__ since they are classes, not modules
                # __all__ should only contain module names, individual components are accessible via __getattr__

        _discovered_modules.add(module_name)

    except (ImportError, AttributeError):
        # If import fails, mark as discovered to avoid retrying
        _discovered_modules.add(module_name)


# Static base __all__ with module names
__all__ = [
    "chains",
    "custom_component",
    "data",
    "deactivated",
    "documentloaders",
    "embeddings",
    "files_ingestion",
    "helpers",
    "homeassistant",
    "huggingface",
    "icosacomputing",
    "input_output",
    "langchain_utilities",
    "link_extractors",
    "logic",
    "models_and_agents",
    "output_parsers",
    "processing",
    "prototypes",
    "textsplitters",
    "toolkits",
    "tools",
    "vectorstores",
    "yahoosearch",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import component modules or individual components on attribute access.

    Supports both:
    - components.agents (module access)
    - components.AgentComponent (direct component access)

    Uses on-demand discovery - only scans modules when components are requested.
    """
    # First check if we already know about this attribute
    if attr_name not in _dynamic_imports:
        # Try to discover components from modules that might have this component
        # Get all module names we haven't discovered yet
        undiscovered_modules = [
            name
            for name in _dynamic_imports
            if _dynamic_imports[name] == "__module__" and name not in _discovered_modules and name != "notion"
        ]

        # Discover components from undiscovered modules
        # Try all undiscovered modules until we find the component or exhaust the list
        for module_name in undiscovered_modules:
            _discover_components_from_module(module_name)
            # Check if we found what we're looking for
            if attr_name in _dynamic_imports:
                break

    # If still not found, try to resolve as an extracted bundle.  The
    # mass-extraction moved many former in-tree categories into
    # standalone ``lfx-<bundle>`` distributions whose import path is
    # ``lfx_<bundle>.components.<bundle>``.  Saved flows and the
    # backwards-compat shim in ``langflow.components`` expect
    # ``getattr(lfx.components, '<bundle>')`` to return the bundle
    # package; resolve the import on first access and cache.
    if attr_name not in _dynamic_imports:
        bundle_pkg_name = f"lfx_{attr_name}.components.{attr_name}"
        try:
            import importlib

            result = importlib.import_module(bundle_pkg_name)
        except ImportError:
            msg = f"module '{__name__}' has no attribute '{attr_name}'"
            raise AttributeError(msg) from None
        globals()[attr_name] = result
        return result

    try:
        module_path = _dynamic_imports[attr_name]

        if module_path == "__module__":
            # This is a module import (e.g., components.agents)
            result = import_mod(attr_name, "__module__", __spec__.parent)
            # After importing a module, discover its components
            _discover_components_from_module(attr_name)
        elif "." in module_path:
            # This is a component import (e.g., components.AgentComponent -> agents.agent)
            module_name, component_file = module_path.split(".", 1)
            # Check if this is an alias module (data, helpers, logic, models)
            # These modules forward to other modules, so we need to import directly from the module
            # instead of trying to import from a submodule that doesn't exist
            if module_name in ("data", "helpers", "logic", "models"):
                # For alias modules, import the module and get the component directly
                alias_module = import_mod(module_name, "__module__", __spec__.parent)
                result = getattr(alias_module, attr_name)
            else:
                # Import the specific component from its module
                result = import_mod(attr_name, component_file, f"{__spec__.parent}.{module_name}")
        else:
            # Fallback to regular import
            result = import_mod(attr_name, module_path, __spec__.parent)

    except (ImportError, AttributeError) as e:
        # Check if this is a missing dependency issue by looking at the error message
        if "No module named" in str(e):
            # Extract the missing module name and suggest installation
            import re

            match = re.search(r"No module named '([^']+)'", str(e))
            if match:
                missing_module = match.group(1)
                msg = f"Could not import '{attr_name}' from '{__name__}'. Missing dependency: '{missing_module}'. "
            else:
                msg = f"Could not import '{attr_name}' from '{__name__}'. Missing dependencies: {e}"
        elif "cannot import name" in str(e):
            msg = f"Could not import '{attr_name}' from '{__name__}'. Import error: {e}"
        else:
            msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e

    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    """Listing of in-tree categories + installed bundle names.

    Bundle names are discovered via the ``langflow.extensions`` entry
    point so the listing stays in sync with whatever ``lfx-*``
    distributions are installed (no static list to maintain).
    Falls back silently if the entry-point scan fails -- the dir is
    informational and must never block the import.
    """
    items = list(__all__)
    try:
        from importlib.metadata import entry_points

        # Distribution names follow ``lfx-<bundle>``; the bundle
        # category name is the distribution suffix with hyphens
        # mapped to underscores.
        items.extend(
            ep.name[len("lfx-") :].replace("-", "_")
            for ep in entry_points(group="langflow.extensions")
            if ep.name.startswith("lfx-")
        )
    except Exception as _err:  # noqa: BLE001 - dir() must never block on diagnostics
        # The listing is informational; downstream callers (IDE
        # autocomplete, dir() prints) prefer an incomplete list over
        # an exception.
        _ = _err
    return sorted(set(items))
