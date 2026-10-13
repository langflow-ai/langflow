"""Keep named project types out of the generic declaration/save/archive/form paths.

Scope is explicit. Built-in declarations, runtime graph codecs, research builders,
type-specific routers and their tests may name the types they implement. This is
not a global ban on domain vocabulary or a Python plugin sandbox.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIALIZED_TYPES = frozenset({"agent-harness", "tool-pack", "skill-pack", "eval-suite"})
GENERIC_FILES = (
    "src/lfx/src/lfx/projects/schema.py",
    "src/lfx/src/lfx/projects/registry.py",
    "src/lfx/src/lfx/projects/lifecycle.py",
    "src/lfx/src/lfx/projects/writer.py",
    "src/lfx/src/lfx/projects/archives.py",
    "src/lfx/src/lfx/projects/archive_config.py",
    "src/lfx/src/lfx/projects/archive_context.py",
    "src/lfx/src/lfx/projects/starters.py",
    "src/backend/base/langflow/services/database/models/folder/config_writer.py",
    "src/backend/base/langflow/services/database/models/folder/save_context.py",
    "src/backend/base/langflow/services/database/models/folder/save_hooks.py",
    "src/backend/base/langflow/services/database/models/folder/utils.py",
    "src/backend/base/langflow/api/v1/projects.py",
    "src/backend/base/langflow/api/v1/projects_files.py",
    "src/backend/base/langflow/api/v1/project_compositions.py",
    "src/backend/base/langflow/api/v1/project_type_guards.py",
    "src/frontend/src/pages/MainPage/pages/harnessPage/harness-page.tsx",
    "src/frontend/src/pages/MainPage/pages/harnessPage/project-field-widgets.tsx",
    "src/frontend/src/pages/MainPage/components/header/index.tsx",
)


def _type_selector(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in {"project_type", "type_name"}
    if isinstance(node, ast.Attribute):
        return node.attr in {"project_type", "type_name"} or (
            node.attr == "name"
            and isinstance(node.value, ast.Name)
            and node.value.id in {"definition", "project_type", "type", "candidate"}
        )
    if isinstance(node, ast.Subscript):
        return isinstance(node.slice, ast.Constant) and node.slice.value == "project_type"
    return False


def violations(source: str, *, suffix: str) -> list[tuple[int, str]]:
    """Return offending literal locations; ignore prose and ordinary `flows` data keys."""
    found = set()
    if suffix == ".py":
        tree = ast.parse(source)
        docstrings = {
            id(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value in SPECIALIZED_TYPES
                and id(node) not in docstrings
            ):
                found.add((node.lineno, node.value))
            # `flows` is also an archive mode and a graph key. Refuse it when used
            # as an actual type selector, rather than banning unrelated JSON shapes.
            if isinstance(node, ast.Compare) and _type_selector(node.left):
                for comparator in node.comparators:
                    for value in ast.walk(comparator):
                        if isinstance(value, ast.Constant) and value.value == "flows":
                            found.add((value.lineno, "flows"))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "get_project_type":
                for value in node.args:
                    if isinstance(value, ast.Constant) and value.value == "flows":
                        found.add((value.lineno, "flows"))
    else:
        tokens = re.compile(r"""//[^\n]*|/\*[\s\S]*?\*/|(?P<quote>["'`])(?P<value>(?:\\.|(?!\1)[^\\])*?)(?P=quote)""")
        for match in tokens.finditer(source):
            if match.group("quote") and match.group("value") in SPECIALIZED_TYPES:
                found.add((source.count("\n", 0, match.start()) + 1, match.group("value")))
        for match in re.finditer(r"""(?:project_type|projectType)\s*[!=]==?\s*["'`]flows["'`]""", source):
            found.add((source.count("\n", 0, match.start()) + 1, "flows"))
    return sorted(found)


def check(root: Path = ROOT) -> list[str]:
    errors = []
    for name in GENERIC_FILES:
        path = root / name
        if not path.is_file():
            errors.append(f"{name}: scoped infrastructure file is missing; update the boundary check")
            continue
        errors.extend(
            f"{name}:{line}: generic infrastructure names {value!r}"
            for line, value in violations(path.read_text(), suffix=path.suffix)
        )
    return errors


if __name__ == "__main__":
    problems = check()
    if problems:
        print("\n".join(problems))
        raise SystemExit(1)
    print(f"Project type boundaries passed ({len(GENERIC_FILES)} infrastructure files).")
