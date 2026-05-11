"""Generate requirements.txt from a Langflow flow JSON.

Analyzes a flow's component code and configuration to determine the minimal
set of PyPI packages needed to run that flow on a standalone LFX runner.

Uses ``importlib.metadata`` to dynamically resolve import names to PyPI
distribution names and to compute the transitive dependency tree of ``lfx``,
eliminating the need for static mapping tables.

Known limitations
-----------------
* **String-based dynamic imports** — ``importlib.import_module(variable)``,
  ``exec()``, and ``__import__()`` are invisible to AST analysis.  If a custom
  component loads a package this way, it will not appear in the output.
* **PythonREPLTool ``global_imports`` field** — The ``PythonREPLTool``
  component accepts a comma-separated string of module names in a template
  field.  These are imported at runtime via ``importlib.import_module()`` and
  are not detected.
* **Cross-platform versions** — Versions are pinned from the *current*
  environment.  Packages pinned on macOS may lack Linux wheels (or vice versa)
  and a pin from Python 3.12 may not install on 3.10.
* **System-level dependencies** — Native libraries required by Python packages
  (e.g. ``libpq-dev`` for ``psycopg2``) cannot be expressed in
  ``requirements.txt``.
* **``--lfx-package`` and transitive filtering** — The ``lfx_package`` parameter
  controls only the output name (e.g. ``lfx-nightly``).  The "already provided
  by lfx" filter always resolves against the ``lfx`` distribution installed in
  the current environment.  If the alternative distribution has different
  transitive dependencies, the output may include extra or missing packages.
"""

from __future__ import annotations

import ast
import importlib.metadata as md
import inspect
import json
import re
import sys
import warnings
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

# ---------------------------------------------------------------------------
# Standard-library module names (3.10+)
# ---------------------------------------------------------------------------
try:
    STDLIB_MODULES: frozenset[str] = frozenset(sys.stdlib_module_names)
except AttributeError:
    STDLIB_MODULES = frozenset(sys.builtin_module_names)

# ---------------------------------------------------------------------------
# Import name → PyPI name overrides for packages where the import name
# is completely different from the PyPI name and can't be guessed by the
# underscore-to-hyphen fallback.  This is only needed when the package
# is not installed (so packages_distributions() can't resolve it).
# ---------------------------------------------------------------------------
IMPORT_NAME_OVERRIDES: dict[str, str] = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "googleapiclient": "google-api-python-client",
    "mem0": "mem0ai",
    "sklearn": "scikit-learn",
    "attr": "attrs",
    "gi": "PyGObject",
    "serial": "pyserial",
}

# ---------------------------------------------------------------------------
# Additional runtime deps that certain imports pull in but are not visible
# in the component's own import statements.
# ---------------------------------------------------------------------------
MODULE_EXTRA_DEPS: dict[str, list[str]] = {
    "bs4": ["lxml", "tabulate"],
}

# Import names that are internal to the lfx/langflow runtime and should
# never appear as separate requirements.
_INTERNAL_IMPORT_NAMES: frozenset[str] = frozenset({"lfx", "langflow", "langflow_base"})

# Fields in a component template that may contain provider selection info
# NOTE: Look back into how the dynamic components (LanguageModel, EmbeddingModel) are handled.
# Currently, these two make dependency extraction more complex by requiring
# this "guesswork" on what models are being used.
_MODEL_FIELDS = {"model", "agent_llm", "embeddings_model", "embedding_model"}

# Fallback provider → package mapping for providers whose component class may
# not be importable in every environment (e.g. Azure OpenAI shares
# langchain-openai with the regular OpenAI provider).
_PROVIDER_PACKAGE_FALLBACKS: dict[str, set[str]] = {
    "Azure OpenAI": {"langchain-openai"},
}


# ===================================================================
# Dynamic resolution via importlib.metadata
# ===================================================================


@lru_cache(maxsize=1)
def _get_import_to_dist_map() -> MappingProxyType[str, list[str]]:
    """Return the mapping of importable names → distribution names.

    Uses ``importlib.metadata.packages_distributions()`` which reverse-maps
    every importable top-level name to the distribution(s) that provide it.
    For example: ``{'PIL': ['pillow'], 'yaml': ['PyYAML'], ...}``.

    Returns a read-only ``MappingProxyType`` so that callers cannot
    accidentally mutate the cached result.
    """
    try:
        return MappingProxyType(md.packages_distributions())
    except AttributeError:
        warnings.warn(
            "importlib.metadata.packages_distributions() not available. "
            "Package resolution will use heuristic fallbacks.",
            stacklevel=2,
        )
        return MappingProxyType({})
    except (OSError, ValueError) as exc:
        warnings.warn(
            f"Failed to read package metadata: {exc}. Package resolution will use heuristic fallbacks.",
            stacklevel=2,
        )
        return MappingProxyType({})


def _normalize_dist(name: str) -> str:
    """Normalize a distribution name for comparison (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _pin_version(package_name: str) -> str:
    """Return ``package_name==X.Y.Z`` if the package is installed, else bare name."""
    try:
        version = md.version(package_name)
    except md.PackageNotFoundError:
        warnings.warn(
            f"Could not determine installed version for '{package_name}'. It will be included without a version pin.",
            stacklevel=2,
        )
        return package_name
    return f"{package_name}=={version}"


@lru_cache(maxsize=1)
def _get_lfx_transitive_dists() -> frozenset[str]:
    """Compute the full transitive closure of distributions provided by lfx.

    Recursively walks ``importlib.metadata.requires()`` to build the set of
    all distribution names (normalized) that are already satisfied by
    installing the ``lfx`` package.
    """

    def _collect(dist_name: str, seen: set[str]) -> None:
        norm = _normalize_dist(dist_name)
        if norm in seen:
            return
        seen.add(norm)
        try:
            reqs = md.requires(dist_name) or []
        except md.PackageNotFoundError:
            return
        for req in reqs:
            if "extra ==" in req:
                continue  # skip optional/extra dependencies
            child = re.split(r"[<>=~!\[; ]", req)[0].strip()
            if child:
                _collect(child, seen)

    seen: set[str] = set()
    _collect("lfx", seen)
    return frozenset(seen)


@lru_cache(maxsize=1)
def _get_lfx_provided_imports() -> frozenset[str]:
    """Build the set of import names transitively provided by lfx.

    Combines ``packages_distributions()`` with the transitive dependency tree
    to determine which import names are already available after
    ``pip install lfx``.
    """
    lfx_dists = _get_lfx_transitive_dists()
    import_map = _get_import_to_dist_map()

    provided: set[str] = set()
    for import_name, dist_names in import_map.items():
        for dist in dist_names:
            if _normalize_dist(dist) in lfx_dists:
                provided.add(import_name)
                break
    return frozenset(provided)


def _import_to_package(import_name: str) -> str:
    """Map a Python import name to its PyPI distribution name.

    Resolution order:
    1. ``importlib.metadata.packages_distributions()`` (authoritative, live)
    2. ``IMPORT_NAME_OVERRIDES`` (non-guessable names for packages that may
       not be installed in the current environment)
    3. Underscore-to-hyphen convention (covers most remaining cases)
    """
    import_map = _get_import_to_dist_map()
    dist_names = import_map.get(import_name)
    if dist_names:
        return dist_names[0]  # first (primary) distribution
    # Check the override table for non-guessable names
    if import_name in IMPORT_NAME_OVERRIDES:
        return IMPORT_NAME_OVERRIDES[import_name]
    # Fallback: replace underscores with hyphens (covers most packages)
    return import_name.replace("_", "-")


# ===================================================================
# AST-based import extraction
# ===================================================================


def _extract_imports(source: str) -> set[str]:
    """Extract top-level package names from all imports in Python source via AST.

    Walks the entire AST (including function bodies and try/except blocks) so
    that lazy imports inside ``build_model()`` etc. are captured.  Returns only
    the first segment of each dotted import (e.g. ``foo`` from ``import foo.bar``).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        warnings.warn(
            f"Could not parse component source (SyntaxError: {exc}). "
            "Imports from this component will not be included in requirements.",
            stacklevel=2,
        )
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                # Relative import - skip (internal to the component)
                continue
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


# ===================================================================
# Template / provider detection
# ===================================================================


def _resolve_provider_packages(provider_name: str) -> set[str]:
    """Dynamically resolve PyPI packages needed for a model provider.

    Uses ``MODEL_PROVIDERS_DICT`` to look up the provider's component instance,
    then inspects its class's source module to extract import statements.  This
    avoids maintaining a static provider→package mapping table.

    This is specifically necessary because the ``LanguageModelComponent`` delegates
    to provider-specific components (e.g. ``OpenAIModelComponent``) that dynamically
    import the actual model class at runtime.

    Note: only the component's own module is inspected, not parent classes.
    Parent classes (e.g. ``LCModelComponent``) are all part of lfx, so any
    imports they introduce are already in lfx's transitive dependency tree
    and would be filtered out regardless.
    """
    try:
        from lfx.base.models.model_input_constants import MODEL_PROVIDERS_DICT
    except ImportError:
        warnings.warn(
            f"Could not import MODEL_PROVIDERS_DICT. Provider '{provider_name}' packages will not be resolved.",
            stacklevel=2,
        )
        return set()

    provider_info = MODEL_PROVIDERS_DICT.get(provider_name)
    if not provider_info:
        fallback = _PROVIDER_PACKAGE_FALLBACKS.get(provider_name)
        if fallback:
            return set(fallback)
        warnings.warn(
            f"Provider '{provider_name}' was detected in the flow but is not "
            "registered in MODEL_PROVIDERS_DICT (its package may not be installed). "
            "Its dependencies will not be included in requirements.",
            stacklevel=2,
        )
        return set()

    component_instance = provider_info.get("component_class")
    if component_instance is None:
        warnings.warn(
            f"Provider '{provider_name}' has no component instance in MODEL_PROVIDERS_DICT. "
            "Its dependencies will not be included in requirements.",
            stacklevel=2,
        )
        return set()

    try:
        module = inspect.getmodule(type(component_instance))
        if module is None:
            warnings.warn(
                f"Could not locate source module for provider '{provider_name}'. "
                "Its dependencies will not be included in requirements.",
                stacklevel=2,
            )
            return set()
        source = inspect.getsource(module)
    except (OSError, TypeError) as exc:
        warnings.warn(
            f"Could not inspect source for provider '{provider_name}': {exc}. "
            "Its dependencies will not be included in requirements.",
            stacklevel=2,
        )
        return set()

    imports = _extract_imports(source)
    lfx_provided = _get_lfx_provided_imports()
    packages: set[str] = set()
    for imp in imports:
        if imp in STDLIB_MODULES or imp in _INTERNAL_IMPORT_NAMES:
            continue
        if imp in MODULE_EXTRA_DEPS:
            for extra in MODULE_EXTRA_DEPS[imp]:
                packages.add(extra)
        if imp in lfx_provided:
            continue
        packages.add(_import_to_package(imp))
    return packages


def _resolve_embedding_provider_packages(provider_name: str) -> set[str]:
    """Resolve PyPI packages needed for an embedding model provider.

    The ``EmbeddingModelComponent`` follows the same dynamic-import pattern as
    the ``LanguageModelComponent``: its code field only imports from ``lfx``
    internals, while the actual provider package (e.g. ``langchain-openai``) is
    imported at runtime via ``get_embedding_class()``.

    This function bridges that gap by chaining two registries from
    ``unified_models.py``:

    1. ``EMBEDDING_PROVIDER_CLASS_MAPPING``: provider name → embedding class name
    2. ``_EMBEDDING_CLASS_IMPORTS``: class name → (module_path, attr, install_hint)

    Because both registries live in ``unified_models.py``, adding a new
    embedding provider there automatically makes it visible here — no
    separate mapping to maintain.
    """
    try:
        from lfx.base.models.unified_models import (
            _EMBEDDING_CLASS_IMPORTS,
            EMBEDDING_PROVIDER_CLASS_MAPPING,
        )
    except ImportError:
        warnings.warn(
            "Could not import embedding registries from unified_models. "
            f"Embedding packages for provider '{provider_name}' will not be resolved.",
            stacklevel=2,
        )
        return set()

    class_name = EMBEDDING_PROVIDER_CLASS_MAPPING.get(provider_name)
    if not class_name:
        # This provider has no embedding support (e.g. Anthropic, Groq).
        # This is expected — not a warning — since this function is called
        # for every detected provider, including language-model-only ones.
        return set()

    import_info = _EMBEDDING_CLASS_IMPORTS.get(class_name)
    if not import_info:
        warnings.warn(
            f"Embedding class '{class_name}' for provider '{provider_name}' is in "
            "EMBEDDING_PROVIDER_CLASS_MAPPING but not in _EMBEDDING_CLASS_IMPORTS. "
            "The import registry in unified_models.py may need updating.",
            stacklevel=2,
        )
        return set()

    module_path, _attr_name, install_hint = import_info

    # Use install_hint if provided (handles internal module paths like lfx.base.models.*)
    if install_hint:
        return {install_hint}

    top_level = module_path.split(".")[0]
    if top_level in STDLIB_MODULES or top_level in _INTERNAL_IMPORT_NAMES:
        return set()

    lfx_provided = _get_lfx_provided_imports()
    if top_level in lfx_provided:
        return set()

    return {_import_to_package(top_level)}


def _detect_providers_from_template(template: dict) -> set[str]:
    """Detect model providers from a component's template field values.

    Looks at model-selection fields (e.g., ``model``, ``agent_llm``) and
    extracts the ``provider`` string when the field is configured.
    """
    providers: set[str] = set()
    for field_name in _MODEL_FIELDS:
        field = template.get(field_name)
        if not isinstance(field, dict):
            continue
        value = field.get("value")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "provider" in item:
                    providers.add(item["provider"])
        elif isinstance(value, dict) and "provider" in value:
            providers.add(value["provider"])
    return providers


# ===================================================================
# Per-node analysis
# ===================================================================


def _extract_component_requirements(node: dict) -> tuple[set[str], set[str]]:
    """Extract requirements from a single flow node.

    Returns:
        A tuple of (package_names, provider_names) where package_names are
        PyPI packages required by the component code and provider_names are
        model provider strings detected from the template configuration.
    """
    packages: set[str] = set()

    node_data = node.get("data", {})
    node_info = node_data.get("node", {})
    template = node_info.get("template", {})

    lfx_provided = _get_lfx_provided_imports()

    # --- 1. Static analysis: parse the component code ---
    code_field = template.get("code")
    if isinstance(code_field, dict):
        source = code_field.get("value")
        if source and isinstance(source, str):
            imports = _extract_imports(source)
            for imp in imports:
                # Skip stdlib
                if imp in STDLIB_MODULES:
                    continue
                # Skip lfx / langflow internal imports - lfx provides these
                # interfaces at runtime so they should never be listed as
                # separate requirements.
                if imp in _INTERNAL_IMPORT_NAMES:
                    continue

                # Always check extra runtime deps (e.g. bs4 → lxml, tabulate)
                # even if the import itself is provided by lfx, because the
                # extras may not be.
                if imp in MODULE_EXTRA_DEPS:
                    for extra in MODULE_EXTRA_DEPS[imp]:
                        packages.add(extra)

                # Skip imports already provided by lfx
                if imp in lfx_provided:
                    continue

                pkg = _import_to_package(imp)
                packages.add(pkg)

    # --- 2. Dynamic analysis: detect provider from template fields ---
    providers = _detect_providers_from_template(template)

    return packages, providers


# ===================================================================
# Public API
# ===================================================================


def generate_requirements_from_flow(
    flow: dict,
    *,
    lfx_package: str = "lfx",
    include_lfx: bool = True,
    pin_versions: bool = True,
) -> list[str]:
    """Generate a requirements list from a Langflow flow JSON.

    Args:
        flow: Parsed Langflow flow JSON (dict).
        lfx_package: Name of the LFX package to include (e.g. ``"lfx"`` or
            ``"lfx-nightly"``).
        include_lfx: Whether to include the LFX package itself.
        pin_versions: If True, pin each package to the version currently
            installed in this environment (``pkg==X.Y.Z``).  Falls back to
            an unpinned name when the package is not installed.

    Returns:
        Sorted list of PyPI package specifiers needed to run this flow.
    """
    all_packages: set[str] = set()
    all_providers: set[str] = set()

    data = flow.get("data", {})
    nodes = data.get("nodes", [])

    for node in nodes:
        # Skip note nodes (annotations, not executable components)
        if node.get("type") == "noteNode":
            continue

        packages, providers = _extract_component_requirements(node)
        all_packages.update(packages)
        all_providers.update(providers)

    # Add provider-specific packages (resolved dynamically from component source)
    for provider in all_providers:
        all_packages.update(_resolve_provider_packages(provider))
        all_packages.update(_resolve_embedding_provider_packages(provider))

    fmt = _pin_version if pin_versions else lambda p: p

    # Build final sorted list
    result: list[str] = []
    if include_lfx:
        result.append(fmt(lfx_package))
    result.extend(sorted(fmt(p) for p in all_packages))

    return result


def generate_requirements_txt(
    flow: dict,
    *,
    lfx_package: str = "lfx",
    include_lfx: bool = True,
    pin_versions: bool = True,
) -> str:
    """Generate requirements.txt content from a Langflow flow JSON.

    Args:
        flow: Parsed Langflow flow JSON (dict).
        lfx_package: Name of the LFX package to include.
        include_lfx: Whether to include the LFX package itself.
        pin_versions: If True, pin each package to the currently installed
            version.

    Returns:
        String content suitable for writing to a requirements.txt file.
    """
    reqs = generate_requirements_from_flow(
        flow,
        lfx_package=lfx_package,
        include_lfx=include_lfx,
        pin_versions=pin_versions,
    )
    lines = [
        "# Auto-generated requirements for Langflow flow",
        "# This file contains only the dependencies needed for this specific flow",
        "",
    ]
    lines.extend(reqs)
    lines.append("")  # trailing newline
    return "\n".join(lines)


def generate_requirements_from_file(
    flow_path: str | Path,
    *,
    lfx_package: str = "lfx",
    include_lfx: bool = True,
    pin_versions: bool = True,
) -> list[str]:
    """Generate requirements list from a flow JSON file path.

    Args:
        flow_path: Path to a Langflow flow JSON file.
        lfx_package: Name of the LFX package to include.
        include_lfx: Whether to include the LFX package itself.
        pin_versions: If True, pin each package to the currently installed
            version.

    Returns:
        Sorted list of PyPI package specifiers.
    """
    path = Path(flow_path)
    flow = json.loads(path.read_text(encoding="utf-8"))
    return generate_requirements_from_flow(
        flow,
        lfx_package=lfx_package,
        include_lfx=include_lfx,
        pin_versions=pin_versions,
    )
