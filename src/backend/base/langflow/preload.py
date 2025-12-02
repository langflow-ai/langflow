"""Preload all langflow modules and components into memory.

This module provides utilities to force-load all langflow dependencies,
modules, and components into RAM upfront.
"""

import importlib
import pkgutil
from typing import Any


def preload_all_modules() -> None:
    """Force import all langflow compatibility modules.

    This triggers the lazy loading of all modules defined in the
    compatibility layer, ensuring they're loaded into memory.
    """
    import langflow  # noqa: F401

    # All modules from module_mappings in __init__.py
    modules_to_load = [
        # Core modules
        "langflow.base",
        "langflow.inputs",
        "langflow.inputs.inputs",
        "langflow.schema",
        "langflow.schema.data",
        "langflow.schema.serialize",
        "langflow.template",
        "langflow.template.field",
        "langflow.template.field.base",
        "langflow.components",
        "langflow.components.helpers",
        "langflow.components.helpers.calculator_core",
        "langflow.components.helpers.create_list",
        "langflow.components.helpers.current_date",
        "langflow.components.helpers.id_generator",
        "langflow.components.helpers.memory",
        "langflow.components.helpers.output_parser",
        "langflow.components.helpers.store_message",
        # Base submodules
        "langflow.base.agents",
        "langflow.base.chains",
        "langflow.base.data",
        "langflow.base.data.utils",
        "langflow.base.document_transformers",
        "langflow.base.embeddings",
        "langflow.base.flow_processing",
        "langflow.base.io",
        "langflow.base.io.chat",
        "langflow.base.io.text",
        "langflow.base.langchain_utilities",
        "langflow.base.memory",
        "langflow.base.models",
        "langflow.base.models.google_generative_ai_constants",
        "langflow.base.models.openai_constants",
        "langflow.base.models.anthropic_constants",
        "langflow.base.models.aiml_constants",
        "langflow.base.models.aws_constants",
        "langflow.base.models.groq_constants",
        "langflow.base.models.novita_constants",
        "langflow.base.models.ollama_constants",
        "langflow.base.models.sambanova_constants",
        "langflow.base.models.cometapi_constants",
        "langflow.base.prompts",
        "langflow.base.prompts.api_utils",
        "langflow.base.prompts.utils",
        "langflow.base.textsplitters",
        "langflow.base.tools",
        "langflow.base.vectorstores",
        # Langflow-only modules
        "langflow.base.data.kb_utils",
        "langflow.base.knowledge_bases",
        "langflow.components.knowledge_bases",
    ]

    for module_name in modules_to_load:
        try:
            importlib.import_module(module_name)
        except (ImportError, AttributeError):
            # Skip modules that don't exist
            continue


def preload_all_components() -> dict[str, Any]:
    """Force load all components into memory.

    Returns:
        Dictionary of all loaded components by category.
    """
    try:
        from lfx.custom.utils import get_all_types_dict
        from lfx.constants import BASE_COMPONENTS_PATH

        # Load all components (native + custom)
        components_paths = [BASE_COMPONENTS_PATH]
        return get_all_types_dict(components_paths)
    except ImportError:
        return {}


async def apreload_all_components() -> dict[str, Any]:
    """Force load all components into memory (async version).

    Returns:
        Dictionary of all loaded components by category.
    """
    try:
        from lfx.interface.components import aget_all_types_dict
        from lfx.constants import BASE_COMPONENTS_PATH

        # Load all components (native + custom)
        components_paths = [BASE_COMPONENTS_PATH]
        return await aget_all_types_dict(components_paths)
    except ImportError:
        return {}


def preload_all_submodules(package_name: str) -> None:
    """Recursively import all submodules of a package.

    Args:
        package_name: Name of the package to preload.
    """
    try:
        package = importlib.import_module(package_name)
        if not hasattr(package, "__path__"):
            return

        for _, modname, _ in pkgutil.walk_packages(
            package.__path__, prefix=package.__name__ + "."
        ):
            try:
                importlib.import_module(modname)
            except (ImportError, AttributeError):
                continue
    except ImportError:
        pass


def preload_everything() -> dict[str, Any]:
    """Preload all langflow modules, components, and dependencies.

    This is the main function to call if you want to load everything
    into RAM upfront.

    Returns:
        Dictionary containing all loaded components.
    """
    # Load all compatibility modules
    preload_all_modules()

    # Recursively load all submodules of key packages
    packages_to_walk = [
        "langflow.base",
        "langflow.components",
        "langflow.inputs",
        "langflow.schema",
        "langflow.template",
    ]

    for package in packages_to_walk:
        try:
            preload_all_submodules(package)
        except Exception:
            continue

    # Load all components
    components = preload_all_components()

    return components


async def apreload_everything() -> dict[str, Any]:
    """Preload all langflow modules, components, and dependencies (async version).

    This is the async version of preload_everything().

    Returns:
        Dictionary containing all loaded components.
    """
    # Load all compatibility modules
    preload_all_modules()

    # Recursively load all submodules of key packages
    packages_to_walk = [
        "langflow.base",
        "langflow.components",
        "langflow.inputs",
        "langflow.schema",
        "langflow.template",
    ]

    for package in packages_to_walk:
        try:
            preload_all_submodules(package)
        except Exception:
            continue

    # Load all components (async)
    components = await apreload_all_components()

    return components

