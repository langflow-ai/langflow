"""Dependency analysis utilities for custom components."""

from __future__ import annotations

import ast
import importlib.metadata as md
import importlib.util
import sys
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

try:
    STDLIB_MODULES: set[str] = set(sys.stdlib_module_names)  # 3.10+
except AttributeError:
    # Fallback heuristic if running on <3.10
    STDLIB_MODULES = set(sys.builtin_module_names)


@dataclass(frozen=True)
class DependencyInfo:
    """Information about a dependency imported in Python code."""

    name: str  # package name (e.g. "numpy", "requests")
    version: str | None  # package version if available
    is_local: bool  # True for relative imports (from .module import ...)


@dataclass(frozen=True)
class ImportRef:
    """Represents a parsed import statement."""

    module: str | None
    level: int  # 0 for absolute, >0 for relative


def _top_level(pkg: str) -> str:
    """Extract top-level package name."""
    return pkg.split(".", 1)[0]


def _is_relative(module: str | None) -> bool:
    """Check if module is a relative import."""
    return module is not None and module.startswith(".")


class _ImportVisitor(ast.NodeVisitor):
    """AST visitor to extract import information."""

    def __init__(self):
        self.results: list[DependencyInfo] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            full = alias.name
            dep = DependencyInfo(
                name=_top_level(full),
                version=None,
                is_local=False,  # Regular imports are not local
            )
            self.results.append(dep)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        # Reconstruct full module name with proper relative import handling
        if node.level > 0:
            # Relative import: from .module import x or from ..parent import x
            dots = "." * node.level
            full_module = dots + (node.module or "")
        else:
            # Absolute import: from module import x
            full_module = node.module or ""
        for _alias in node.names:
            dep = DependencyInfo(
                name=_top_level(full_module.lstrip(".")) if full_module else "",
                version=None,
                is_local=_is_relative(full_module),  # Check if it's a relative import
            )
            self.results.append(dep)


class _ImportRefVisitor(ast.NodeVisitor):
    """AST visitor to extract import references for graph scanning."""

    def __init__(self):
        self.results: list[ImportRef] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.results.append(ImportRef(module=alias.name, level=0))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        self.results.append(ImportRef(module=node.module, level=node.level))


def _get_package_root(package_name: str) -> Path | None:
    """Resolve a package root using importlib, works for source or pip installs."""
    spec = importlib.util.find_spec(package_name)
    if spec is None:
        return None
    if spec.submodule_search_locations:
        return Path(next(iter(spec.submodule_search_locations)))
    if spec.origin:
        return Path(spec.origin).parent
    return None


@lru_cache(maxsize=1)
def _get_internal_package_names() -> set[str]:
    """Return internal package names available for scanning."""
    packages: set[str] = set()
    for package_name in ("lfx", "langflow"):
        if _get_package_root(package_name) is not None:
            packages.add(package_name)
    return packages


@lru_cache(maxsize=4096)
def _get_module_source(module: str) -> str | None:
    """Return module source without importing it."""
    try:
        spec = importlib.util.find_spec(module)
    except ValueError:
        return None
    if spec is None or spec.loader is None:
        return None
    try:
        source = spec.loader.get_source(module)
    except Exception:  # noqa: BLE001
        source = None
    return source


def _resolve_relative_import(current_module: str, module: str | None, level: int) -> str | None:
    """Resolve a relative import to an absolute module name."""
    if level <= 0:
        return None
    parts = current_module.split(".")
    if level > len(parts):
        return None
    base_parts = parts[: -level]
    if module:
        base_parts.extend(module.split("."))
    if not base_parts:
        return None
    return ".".join(base_parts)


@lru_cache(maxsize=2048)
def _analyze_module_import_graph_cached(module: str, *, resolve_versions: bool) -> tuple[DependencyInfo, ...]:
    """Cached module graph analysis result.

    Returns immutable dependency tuples so callers can safely consume cached data.
    """
    internal_packages = _get_internal_package_names()
    if not module:
        return ()
    entry_source = _get_module_source(module)
    if entry_source is None:
        return ()

    visited: set[str] = set()
    external_deps: dict[str, DependencyInfo] = {}
    stack: list[str] = [module]

    while stack:
        current_module = stack.pop()
        if current_module in visited:
            continue
        visited.add(current_module)

        source = _get_module_source(current_module)
        if not source:
            continue

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        visitor = _ImportRefVisitor()
        visitor.visit(tree)

        for imp in visitor.results:
            if imp.level > 0:
                resolved_module = _resolve_relative_import(current_module, imp.module, imp.level)
                if resolved_module:
                    stack.append(resolved_module)
                continue

            module_name = imp.module or ""
            top_level = _top_level(module_name)
            if not top_level or top_level in STDLIB_MODULES:
                continue

            if top_level in internal_packages:
                stack.append(module_name)
                continue

            if top_level not in external_deps:
                dep = DependencyInfo(name=top_level, version=None, is_local=False)
                external_deps[top_level] = _classify_dependency(dep) if resolve_versions else dep

    return tuple(external_deps.values())


def analyze_module_import_graph(module: str, *, resolve_versions: bool = True) -> list[dict]:
    """Analyze dependencies by walking a module's import graph.

    Args:
        module: Fully-qualified module path (e.g., "lfx.components.models_and_agents.language_model")
        resolve_versions: Whether to resolve version information

    Returns:
        List of dependency dictionaries
    """
    return [asdict(d) for d in _analyze_module_import_graph_cached(module, resolve_versions=resolve_versions)]


def analyze_code_import_graph(source: str, *, resolve_versions: bool = True) -> list[dict]:
    """Analyze dependencies by scanning code and traversing internal imports."""
    internal_packages = _get_internal_package_names()
    external_deps: dict[str, DependencyInfo] = {}

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    visitor = _ImportRefVisitor()
    visitor.visit(tree)

    internal_modules_to_scan: set[str] = set()

    for imp in visitor.results:
        if imp.level > 0:
            # Relative imports in embedded code are treated as local.
            continue

        module_name = imp.module or ""
        top_level = _top_level(module_name)
        if not top_level or top_level in STDLIB_MODULES:
            continue

        if top_level in internal_packages:
            internal_modules_to_scan.add(module_name)
            continue

        if top_level not in external_deps:
            dep = DependencyInfo(name=top_level, version=None, is_local=False)
            external_deps[top_level] = _classify_dependency(dep) if resolve_versions else dep

    for module_name in internal_modules_to_scan:
        for dep in analyze_module_import_graph(module_name, resolve_versions=resolve_versions):
            dep_name = dep.get("name")
            if dep_name and dep_name not in external_deps:
                external_deps[dep_name] = DependencyInfo(
                    name=dep_name,
                    version=dep.get("version"),
                    is_local=False,
                )

    return [asdict(d) for d in external_deps.values()]


def _classify_dependency(dep: DependencyInfo) -> DependencyInfo:
    """Resolve version information for external dependencies."""
    version = None
    if not dep.is_local and dep.name:
        version = _get_distribution_version(dep.name)

    return DependencyInfo(
        name=dep.name,
        version=version,
        is_local=dep.is_local,
    )


def analyze_dependencies(source: str, *, resolve_versions: bool = True) -> list[dict]:
    """Return a list[dict] of dependencies imported by the given Python source code.

    Args:
        source: Python source code string
        resolve_versions: Whether to resolve version information

    Returns:
        List of dependency dictionaries
    """
    code = source

    # Parse the code and extract imports
    tree = ast.parse(code)
    visitor = _ImportVisitor()
    visitor.visit(tree)

    # Process and deduplicate dependencies by package name only
    unique_packages: dict[str, DependencyInfo] = {}
    for raw_dep in visitor.results:
        processed_dep = _classify_dependency(raw_dep) if resolve_versions else raw_dep

        # Skip stdlib imports and local imports - we only care about external dependencies
        if processed_dep.name in STDLIB_MODULES or processed_dep.is_local:
            continue

        # Deduplicate by package name only (not full_module)
        if processed_dep.name not in unique_packages:
            unique_packages[processed_dep.name] = processed_dep

    return [asdict(d) for d in unique_packages.values()]


def analyze_component_dependencies(component_code: str) -> dict:
    """Analyze dependencies for a custom component.

    Args:
        component_code: The component's source code

    Returns:
        Dictionary with dependency analysis results
    """
    try:
        deps = analyze_dependencies(component_code, resolve_versions=True)

        return {
            "total_dependencies": len(deps),
            "dependencies": [{"name": d["name"], "version": d["version"]} for d in deps if d["name"]],
        }
    except (SyntaxError, TypeError, ValueError, ImportError):
        # If analysis fails, return minimal info
        return {
            "total_dependencies": 0,
            "dependencies": [],
        }


# Cache the expensive packages_distributions() call globally
@lru_cache(maxsize=1)
def _get_packages_distributions():
    """Cache the expensive packages_distributions() call."""
    try:
        return md.packages_distributions()
    except (OSError, AttributeError, ValueError):
        return {}


# Helper function to cache version lookups for installed distributions
@lru_cache(maxsize=128)
def _get_distribution_version(import_name: str):
    try:
        # Reverse-lookup: which distribution(s) provide this importable name?
        reverse_map = _get_packages_distributions()
        dist_names = reverse_map.get(import_name)
        if not dist_names:
            return None

        # Take the first matching distribution
        dist_name = dist_names[0]
        return md.distribution(dist_name).version
    except (ImportError, AttributeError, OSError, ValueError):
        return None


@lru_cache(maxsize=128)
def get_versioned_package_distributions(package_name: str, version: str | None = None) -> list[str]:
    """Get versioned package distributions for a given package name.

    If a version is provided, it will return a list
    containing the first matching distribution with the provided version.

    If no version is provided, it will return a list
    containing all matching distributions.

    Note: The distributions are resolved from the current Python environment.
    If the package is not installed, it will return an empty list.
    """
    reverse_map = _get_packages_distributions()
    dist_names = reverse_map.get(package_name, [])

    if not dist_names:
        return []

    if version is not None:
        dist_name = dist_names[0]
        return [f"{dist_name}=={version}"]

    versioned_names: list[str] = []
    for dist_name in dist_names:
        try:
            versioned_names.append(f"{dist_name}=={md.distribution(dist_name).version}")
        except Exception: # noqa: BLE001
            versioned_names.append(dist_name)

    return versioned_names
