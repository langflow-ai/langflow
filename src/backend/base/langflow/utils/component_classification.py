"""Utilities for classifying components as core or bundle components.

This module provides functions to extract and cache bundle component names
from the frontend's SIDEBAR_BUNDLES definition, enabling consistent
classification between frontend and backend.
"""

import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_bundle_component_names() -> frozenset[str]:
    """Extract component names from SIDEBAR_BUNDLES in frontend styleUtils.ts.

    This function parses the frontend's styleUtils.ts file to extract the
    authoritative list of bundle component names. The result is cached for
    performance.

    Returns:
        Frozen set of bundle component names (e.g., 'notion', 'openai', 'anthropic').
        Returns an empty frozenset if the file cannot be found or parsed.

    Example:
        >>> bundles = get_bundle_component_names()
        >>> 'notion' in bundles
        True
        >>> 'input_output' in bundles  # This is a core category
        False
    """
    # Auto-discover frontend path from backend
    # This file is at: src/backend/base/langflow/utils/component_classification.py
    # Frontend is at: src/frontend/src/utils/styleUtils.ts
    backend_utils_path = Path(__file__).parent
    backend_langflow_path = backend_utils_path.parent
    backend_base_path = backend_langflow_path.parent
    backend_path = backend_base_path.parent
    src_path = backend_path.parent
    frontend_path = src_path / "frontend" / "src" / "utils" / "styleUtils.ts"

    if not frontend_path.exists():
        return frozenset()

    with frontend_path.open(encoding="utf-8") as f:
        content = f.read()

    # Find SIDEBAR_BUNDLES array
    sidebar_match = re.search(r"export const SIDEBAR_BUNDLES = \[(.*?)\];", content, re.DOTALL)
    if not sidebar_match:
        return frozenset()

    bundles_content = sidebar_match.group(1)

    # Extract name fields using regex
    name_matches = re.findall(r'name:\s*["\']([^"\']+)["\']', bundles_content)

    return frozenset(name_matches)


def is_bundle_component(component_type: str) -> bool:
    """Check if a component type is a bundle component.

    Args:
        component_type: The component type/category name to check.

    Returns:
        True if the component type is a bundle, False if it's a core component.

    Example:
        >>> is_bundle_component('notion')
        True
        >>> is_bundle_component('input_output')
        False
    """
    return component_type in get_bundle_component_names()


def is_core_component(component_type: str) -> bool:
    """Check if a component type is a core component.

    Args:
        component_type: The component type/category name to check.

    Returns:
        True if the component type is a core component, False if it's a bundle.

    Example:
        >>> is_core_component('input_output')
        True
        >>> is_core_component('notion')
        False
    """
    return not is_bundle_component(component_type)
