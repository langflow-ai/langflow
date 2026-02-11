"""Generate requirements.txt from a Langflow flow JSON.

Analyzes a flow's component code and configuration to determine the minimal
set of PyPI packages needed to run that flow on a standalone LFX runner.

Uses ``importlib.metadata`` to dynamically resolve import names to PyPI
distribution names and to compute the transitive dependency tree of ``lfx``,
eliminating the need for static mapping tables.
"""

from __future__ import annotations

import ast
import importlib.metadata as md
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

# ---------------------------------------------------------------------------
# Standard-library module names (3.10+)
# ---------------------------------------------------------------------------
try:
    STDLIB_MODULES: frozenset[str] = frozenset(sys.stdlib_module_names)
except AttributeError:
    STDLIB_MODULES = frozenset(sys.builtin_module_names)

# ---------------------------------------------------------------------------
# Provider name (as it appears in the model field) → required PyPI packages.
# This is Langflow-specific domain knowledge with no standard mapping.
# ---------------------------------------------------------------------------
PROVIDER_PACKAGES: dict[str, list[str]] = {
    "OpenAI": ["langchain-openai"],
    "Anthropic": ["langchain-anthropic"],
    "Google Generative AI": ["langchain-google-genai"],
    "Ollama": ["langchain-ollama"],
    "IBM WatsonX": ["langchain-ibm"],
    "Cohere": ["langchain-cohere"],
    "NVIDIA": ["langchain-nvidia-ai-endpoints"],
    "Mistral AI": ["langchain-mistralai"],
    "SambaNova": ["langchain-sambanova"],
    "Groq": ["langchain-groq"],
}

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

# Fields in a component template that may contain provider selection info
_MODEL_FIELDS = {"model", "agent_llm", "embeddings_model", "embedding_model"}


# ===================================================================
# Dynamic resolution via importlib.metadata
# ===================================================================


@lru_cache(maxsize=1)
def _get_import_to_dist_map() -> dict[str, list[str]]:
    """Return the mapping of importable names → distribution names.

    Uses ``importlib.metadata.packages_distributions()`` which reverse-maps
    every importable top-level name to the distribution(s) that provide it.
    For example: ``{'PIL': ['pillow'], 'yaml': ['PyYAML'], ...}``.
    """
    try:
        return md.packages_distributions()
    except (OSError, AttributeError, ValueError):
        return {}


def _normalize_dist(name: str) -> str:
    """Normalize a distribution name for comparison (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


@lru_cache(maxsize=1)
def _get_lfx_transitive_dists(lfx_dist_name: str = "lfx") -> frozenset[str]:
    """Compute the full transitive closure of distributions provided by lfx.

    Recursively walks ``importlib.metadata.requires()`` to build the set of
    all distribution names (normalized) that are already satisfied by
    installing the lfx package.
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
    _collect(lfx_dist_name, seen)
    return frozenset(seen)


@lru_cache(maxsize=1)
def _get_lfx_provided_imports(lfx_dist_name: str = "lfx") -> frozenset[str]:
    """Build the set of import names transitively provided by lfx.

    Combines ``packages_distributions()`` with the transitive dependency tree
    to determine which import names are already available after
    ``pip install lfx``.
    """
    lfx_dists = _get_lfx_transitive_dists(lfx_dist_name)
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
    """Extract top-level import names from Python source code via AST."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                # Relative import – skip (internal to the component)
                continue
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


# ===================================================================
# Template / provider detection
# ===================================================================


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
                # Skip lfx-internal imports
                if imp == "lfx":
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
) -> list[str]:
    """Generate a requirements list from a Langflow flow JSON.

    Args:
        flow: Parsed Langflow flow JSON (dict).
        lfx_package: Name of the LFX package to include (e.g. ``"lfx"`` or
            ``"lfx-nightly"``).
        include_lfx: Whether to include the LFX package itself.

    Returns:
        Sorted list of PyPI package names needed to run this flow.
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

    # Add provider-specific packages
    for provider in all_providers:
        provider_pkgs = PROVIDER_PACKAGES.get(provider, [])
        all_packages.update(provider_pkgs)

    # Build final sorted list
    result: list[str] = []
    if include_lfx:
        result.append(lfx_package)
    result.extend(sorted(all_packages))

    return result


def generate_requirements_txt(
    flow: dict,
    *,
    lfx_package: str = "lfx",
    include_lfx: bool = True,
) -> str:
    """Generate requirements.txt content from a Langflow flow JSON.

    Args:
        flow: Parsed Langflow flow JSON (dict).
        lfx_package: Name of the LFX package to include.
        include_lfx: Whether to include the LFX package itself.

    Returns:
        String content suitable for writing to a requirements.txt file.
    """
    reqs = generate_requirements_from_flow(
        flow, lfx_package=lfx_package, include_lfx=include_lfx,
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
) -> list[str]:
    """Generate requirements list from a flow JSON file path.

    Args:
        flow_path: Path to a Langflow flow JSON file.
        lfx_package: Name of the LFX package to include.
        include_lfx: Whether to include the LFX package itself.

    Returns:
        Sorted list of PyPI package names.
    """
    path = Path(flow_path)
    flow = json.loads(path.read_text(encoding="utf-8"))
    return generate_requirements_from_flow(
        flow, lfx_package=lfx_package, include_lfx=include_lfx,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """CLI entry point: ``python -m lfx.utils.flow_requirements <flow.json>``."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate requirements.txt from a Langflow flow JSON.",
    )
    parser.add_argument("flow_json", help="Path to the Langflow flow JSON file")
    parser.add_argument(
        "--lfx-package",
        default="lfx",
        help="Name of the LFX package (default: lfx)",
    )
    parser.add_argument(
        "--no-lfx",
        action="store_true",
        help="Exclude the LFX package from output",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()

    flow_path = Path(args.flow_json)
    if not flow_path.exists():
        print(f"Error: File not found: {flow_path}", file=sys.stderr)
        sys.exit(1)

    flow = json.loads(flow_path.read_text(encoding="utf-8"))
    content = generate_requirements_txt(
        flow,
        lfx_package=args.lfx_package,
        include_lfx=not args.no_lfx,
    )

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        print(f"Requirements written to {args.output}")
    else:
        print(content)


if __name__ == "__main__":
    main()
