"""The scoped architecture check rejects reintroducing built-in type dispatch."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
SPEC = importlib.util.spec_from_file_location(
    "project_type_boundaries", ROOT / "scripts/check_project_type_boundaries.py"
)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def test_generic_project_infrastructure_has_no_named_type_dispatch():
    assert checker.check(ROOT) == []


@pytest.mark.parametrize(
    ("source", "suffix"),
    [
        ('if project.project_type == "agent-harness": pass', ".py"),
        ('handlers = {"tool-pack": save}', ".py"),
        ('if project_type in {"flows"}: pass', ".py"),
        ('get_project_type("flows")', ".py"),
        ('if (projectType === "skill-pack") render();', ".tsx"),
        ('const value = "eval-suite";', ".tsx"),
        ('if (projectType === "flows") render();', ".tsx"),
    ],
)
def test_named_dispatch_is_detected(source, suffix):
    assert checker.violations(source, suffix=suffix)


@pytest.mark.parametrize(
    ("source", "suffix"),
    [
        ('project.get("flows", [])', ".py"),
        ('if definition.archive_format == "flows": pass', ".py"),
        ('"""A tool-pack reference is data."""\npass', ".py"),
        ('// "agent-harness" is explanatory prose\nconst fields = declaration.template;', ".tsx"),
        ('import Panel from "./eval-suite-page";', ".tsx"),
    ],
)
def test_unrelated_graph_keys_and_module_paths_are_allowed(source, suffix):
    assert checker.violations(source, suffix=suffix) == []
