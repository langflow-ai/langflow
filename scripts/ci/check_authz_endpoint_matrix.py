#!/usr/bin/env python3
"""Fail when an authorization-sensitive API route is missing from the OSS matrix."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = REPO_ROOT / "scripts" / "ci" / "authz_endpoint_matrix.json"
API_ROOT = REPO_ROOT / "src" / "backend" / "base" / "langflow"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "websocket"}
ACCESS_MODES = {"authenticated", "conditional", "deprecated", "public"}
REQUIRED_PERSONAS = {
    "viewer",
    "developer",
    "admin",
    "owner",
    "direct_share",
    "team_share",
    "scoped_role",
    "revoked",
}


@dataclass(frozen=True, order=True)
class Route:
    """Stable route identity used by both the AST inventory and the matrix."""

    source: str
    method: str
    path: str
    handler: str

    @property
    def display(self) -> str:
        path = self.path or "<router-root>"
        return f"{self.source}:{self.handler} {self.method} {path}"


def _literal_path(decorator: ast.Call, *, source: str, handler: str) -> str:
    if not decorator.args:
        return ""
    value = decorator.args[0]
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    msg = f"{source}:{handler} uses a non-literal route path; add explicit checker support before merging"
    raise ValueError(msg)


def discover_routes(source: str) -> set[Route]:
    """Return top-level ``@router.<method>`` routes from one API module."""
    path = API_ROOT / source
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    routes: set[Route] = set()
    for node in tree.body:
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            function = decorator.func
            if (
                not isinstance(function, ast.Attribute)
                or not isinstance(function.value, ast.Name)
                or function.value.id != "router"
                or function.attr not in HTTP_METHODS
            ):
                continue
            route = Route(
                source=source,
                method=function.attr.upper(),
                path=_literal_path(decorator, source=source, handler=node.name),
                handler=node.name,
            )
            if route in routes:
                msg = f"duplicate decorated route: {route.display}"
                raise ValueError(msg)
            routes.add(route)
    return routes


def _parse_matrix_route(source: str, raw: str) -> tuple[Route, str, str]:
    try:
        method, path, handler, action, access = raw.split("|")
    except ValueError as exc:
        msg = f"{source}: invalid route entry {raw!r}; expected METHOD|path|handler|action|access"
        raise ValueError(msg) from exc
    if not method or not handler or not action:
        msg = f"{source}: incomplete route entry {raw!r}"
        raise ValueError(msg)
    if access not in ACCESS_MODES:
        msg = f"{source}:{handler}: unknown access mode {access!r}"
        raise ValueError(msg)
    return Route(source=source, method=method, path=path, handler=handler), action, access


def _test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name.startswith("test_")
    }


def _validate_test_reference(raw: str) -> str | None:
    try:
        relative_path, function_name = raw.split("::", 1)
    except ValueError:
        return f"invalid test reference {raw!r}; expected repo/path.py::test_function"
    path = REPO_ROOT / relative_path
    if not path.is_file():
        return f"stale test reference {raw!r}: file does not exist"
    if function_name not in _test_functions(path):
        return f"stale test reference {raw!r}: function does not exist"
    return None


def validate_matrix(matrix_path: Path = DEFAULT_MATRIX) -> list[str]:
    """Return reader-friendly contract errors; an empty list means complete."""
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if matrix.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    presets = matrix.get("persona_presets", {})
    for name, preset in presets.items():
        missing = REQUIRED_PERSONAS - set(preset)
        if missing:
            errors.append(f"persona preset {name!r} is missing {sorted(missing)}")

    expected: set[Route] = set()
    discovered: set[Route] = set()
    for contract in matrix.get("contracts", []):
        missing_fields = {
            "family",
            "source",
            "resource",
            "domain",
            "privacy",
            "side_effects",
            "frontend",
            "personas",
            "test_references",
            "routes",
        } - set(contract)
        if missing_fields:
            errors.append(f"contract {contract.get('family', '<unnamed>')!r} is missing {sorted(missing_fields)}")
            continue
        source = contract["source"]
        preset_name = contract["personas"]
        if preset_name not in presets:
            errors.append(f"{source}: unknown persona preset {preset_name!r}")
        if not contract["test_references"]:
            errors.append(f"{source}: test_references must not be empty")
        errors.extend(
            f"{source}: {error}"
            for reference in contract["test_references"]
            if (error := _validate_test_reference(reference))
        )
        try:
            discovered.update(discover_routes(source))
        except (FileNotFoundError, SyntaxError, ValueError) as exc:
            errors.append(str(exc))
            continue
        for raw in contract["routes"]:
            try:
                route, _action, _access = _parse_matrix_route(source, raw)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if route in expected:
                errors.append(f"matrix classifies route more than once: {route.display}")
            expected.add(route)

    unclassified = discovered - expected
    stale = expected - discovered
    errors.extend(f"unclassified route: {route.display}" for route in sorted(unclassified))
    errors.extend(f"stale matrix route: {route.display}" for route in sorted(stale))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    args = parser.parse_args()
    errors = validate_matrix(args.matrix)
    if errors:
        print("Authorization endpoint matrix validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Authorization endpoint matrix is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
