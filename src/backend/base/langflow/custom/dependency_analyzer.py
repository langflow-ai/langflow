"""Dependency analysis utilities for custom components."""

from __future__ import annotations

import ast
import importlib.metadata as md
import sys
from dataclasses import asdict, dataclass
from functools import lru_cache

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

    def visit_Import(self, node: ast.Import):  # noqa: N802
        for alias in node.names:
            full = alias.name
            dep = DependencyInfo(
                name=_top_level(full),
                version=None,
                is_local=False,  # Regular imports are not local
            )
            self.results.append(dep)

    def visit_ImportFrom(self, node: ast.ImportFrom):  # noqa: N802
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


# Helper function to cache version lookups for installed distributions
@lru_cache(maxsize=128)
def _get_distribution_version(name: str):
    try:
        dist = md.distribution(name)
    except (md.PackageNotFoundError, ImportError, AttributeError):
        return None
    return dist.version
