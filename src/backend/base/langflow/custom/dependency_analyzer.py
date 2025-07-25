"""Dependency analysis utilities for custom components."""

from __future__ import annotations

import ast
import importlib.metadata as md
import sys
from dataclasses import asdict, dataclass

try:
    STDLIB_MODULES: set[str] = set(sys.stdlib_module_names)  # 3.10+
except AttributeError:
    # Fallback heuristic if running on <3.10
    STDLIB_MODULES = set(sys.builtin_module_names)


@dataclass(frozen=True)
class DependencyInfo:
    """Information about a dependency imported in Python code."""

    name: str  # top-level package (e.g. "pydantic")
    full_module: str  # as written in the import (e.g. "pydantic.v1")
    import_type: str  # "import" | "from"
    imported_symbols: tuple[str, ...]  # for "from x import a, b"
    alias: str | None
    version: str | None
    dist_name: str | None
    location: str | None
    is_stdlib: bool
    is_local: bool
    is_optional: bool  # Always False now
    lineno: int


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
                full_module=full,
                import_type="import",
                imported_symbols=(),
                alias=alias.asname,
                version=None,
                dist_name=None,
                location=None,
                is_stdlib=False,  # fill later
                is_local=False,  # fill later
                is_optional=False,  # All imports are required now
                lineno=node.lineno,
            )
            self.results.append(dep)

    def visit_ImportFrom(self, node: ast.ImportFrom):  # noqa: N802
        # node.module can be None for relative imports like "from . import x"
        full_module = node.module if node.module else "." * (node.level or 0)
        for alias in node.names:
            dep = DependencyInfo(
                name=_top_level(full_module.lstrip(".")) if full_module else "",
                full_module=full_module,
                import_type="from",
                imported_symbols=(alias.name,),
                alias=alias.asname,
                version=None,
                dist_name=None,
                location=None,
                is_stdlib=False,  # fill later
                is_local=False,  # fill later
                is_optional=False,  # All imports are required now
                lineno=node.lineno,
            )
            self.results.append(dep)


def _classify_dependency(dep: DependencyInfo) -> DependencyInfo:
    """Classify dependency as stdlib, local, or external and resolve version if possible."""
    # Check if it's a relative import or looks local
    is_local = _is_relative(dep.full_module)

    # Check if it's a stdlib module
    is_stdlib = dep.name in STDLIB_MODULES

    # Try to resolve version for external packages
    version = dist_name = location = None
    if not is_local and not is_stdlib and dep.name:
        try:
            dist = md.distribution(dep.name)
            version = dist.version
            dist_name = dist.metadata["Name"]
            location = str(dist.locate_file(""))
        except (md.PackageNotFoundError, ImportError, AttributeError):
            # If we can't find the package, it might be local or not installed
            pass

    return DependencyInfo(
        name=dep.name,
        full_module=dep.full_module,
        import_type=dep.import_type,
        imported_symbols=dep.imported_symbols,
        alias=dep.alias,
        version=version,
        dist_name=dist_name,
        location=location,
        is_stdlib=is_stdlib,
        is_local=is_local,
        is_optional=False,  # All imports are required now
        lineno=dep.lineno,
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

    # Process and deduplicate dependencies
    unique: dict[tuple[str, str], DependencyInfo] = {}
    for raw_dep in visitor.results:
        processed_dep = _classify_dependency(raw_dep) if resolve_versions else raw_dep

        # Deduplicate by (name, full_module)
        key = (processed_dep.name, processed_dep.full_module)
        if key not in unique:
            unique[key] = processed_dep

    return [asdict(d) for d in unique.values()]


def analyze_component_dependencies(component_code: str) -> dict:
    """Analyze dependencies for a custom component.

    Args:
        component_code: The component's source code

    Returns:
        Dictionary with dependency analysis results
    """
    try:
        deps = analyze_dependencies(component_code, resolve_versions=True)

        # Categorize dependencies
        stdlib_deps = [d for d in deps if d["is_stdlib"]]
        external_deps = [d for d in deps if not d["is_stdlib"] and not d["is_local"]]
        local_deps = [d for d in deps if d["is_local"]]

        return {
            "total_dependencies": len(deps),
            "stdlib_count": len(stdlib_deps),
            "external_count": len(external_deps),
            "local_count": len(local_deps),
            "external_packages": [{"name": d["name"], "version": d["version"]} for d in external_deps if d["name"]],
            "dependencies": deps,
        }
    except (SyntaxError, TypeError, ValueError, ImportError):
        # If analysis fails, return minimal info
        return {
            "total_dependencies": 0,
            "stdlib_count": 0,
            "external_count": 0,
            "local_count": 0,
            "external_packages": [],
            "dependencies": [],
        }
