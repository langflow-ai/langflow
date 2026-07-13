"""Compatibility shims for the extracted ``langflow_services`` package."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

SERVICES_ROOT = Path(__file__).resolve().parents[4] / "langflow-services" / "src" / "langflow_services"
LANGFLOW_SERVICES_ROOT = Path(__file__).resolve().parents[3] / "base" / "langflow" / "services"


def _leaf_shim_modules() -> list[str]:
    modules: list[str] = []
    for path in sorted(LANGFLOW_SERVICES_ROOT.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "sys.modules[__name__] = _impl" not in text:
            continue
        rel = path.relative_to(LANGFLOW_SERVICES_ROOT).with_suffix("")
        modules.append("langflow.services." + ".".join(rel.parts))
    return modules


def _package_shim_modules() -> list[str]:
    modules: list[str] = []
    for path in sorted(LANGFLOW_SERVICES_ROOT.rglob("__init__.py")):
        text = path.read_text(encoding="utf-8")
        if "globals().update" not in text or "Compatibility re-export" not in text:
            continue
        rel = path.parent.relative_to(LANGFLOW_SERVICES_ROOT)
        if not rel.parts:
            continue
        modules.append("langflow.services." + ".".join(rel.parts))
    return modules


@pytest.mark.parametrize("langflow_path", _leaf_shim_modules())
def test_leaf_shim_aliases_services_module(langflow_path: str) -> None:
    services_path = "langflow_services." + langflow_path.removeprefix("langflow.services.")
    host = importlib.import_module(langflow_path)
    pkg = importlib.import_module(services_path)
    assert host is pkg
    assert sys.modules[langflow_path] is pkg


@pytest.mark.parametrize("langflow_path", _package_shim_modules())
def test_package_shim_exports_match_services_package(langflow_path: str) -> None:
    services_path = "langflow_services." + langflow_path.removeprefix("langflow.services.")
    host = importlib.import_module(langflow_path)
    pkg = importlib.import_module(services_path)

    for name in getattr(pkg, "__all__", []):
        assert hasattr(host, name), f"{langflow_path} missing export {name!r}"
        assert getattr(host, name) is getattr(pkg, name)

    if hasattr(pkg, "__getattr__"):
        assert getattr(host, "__getattr__", None) is pkg.__getattr__


def test_watsonx_lazy_package_export_via_langflow_path() -> None:
    """PEP 562 package exports must survive the langflow package shim."""
    mod = importlib.import_module("langflow.services.adapters.deployment.watsonx_orchestrate")
    assert "WatsonxOrchestrateDeploymentService" in mod.__all__
    cls = mod.WatsonxOrchestrateDeploymentService
    from langflow_services.adapters.deployment.watsonx_orchestrate.service import (
        WatsonxOrchestrateDeploymentService,
    )

    assert cls is WatsonxOrchestrateDeploymentService


def test_workflow_exception_pickle_module_path() -> None:
    from langflow.exceptions.api import WorkflowExecutionError

    assert WorkflowExecutionError.__module__ == "langflow.exceptions.api"


def test_services_package_root_exists() -> None:
    assert SERVICES_ROOT.is_dir(), f"missing services package root: {SERVICES_ROOT}"
    assert any(SERVICES_ROOT.rglob("*.py"))


def test_no_static_langflow_imports_in_services_package() -> None:
    dynamic_loaders = frozenset({"import_module", "find_spec", "__import__"})
    violations: list[str] = []
    for path in SERVICES_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                violations.extend(
                    f"{path}:{alias.name}"
                    for alias in node.names
                    if alias.name == "langflow" or alias.name.startswith("langflow.")
                )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and (node.module == "langflow" or node.module.startswith("langflow."))
            ):
                violations.append(f"{path}:{node.module}")
            elif isinstance(node, ast.Call) and node.args:
                func = node.func
                is_dynamic = (isinstance(func, ast.Name) and func.id == "__import__") or (
                    isinstance(func, ast.Attribute) and func.attr in dynamic_loaders
                )
                if not is_dynamic:
                    continue
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    target = arg.value
                    if target == "langflow" or target.startswith("langflow."):
                        violations.append(f"{path}:{target}")
    assert not violations
