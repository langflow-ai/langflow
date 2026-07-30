"""Import and dependency contracts for the built-in LFX component catalog."""

from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path

import pytest
import tomli
from packaging.requirements import Requirement


@pytest.mark.parametrize(
    ("module_name", "blocked_dependency"),
    [
        ("lfx.base.agents.crewai.crew", "litellm"),
        ("lfx.components.tools.calculator", "pytest"),
    ],
)
def test_core_modules_do_not_import_optional_or_test_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    blocked_dependency: str,
) -> None:
    """Core component modules must remain importable in a clean runtime install."""
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == blocked_dependency or name.startswith(f"{blocked_dependency}."):
            error_message = f"No module named '{blocked_dependency}'"
            raise ModuleNotFoundError(error_message, name=blocked_dependency)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    sys.modules.pop(module_name, None)

    importlib.import_module(module_name)


def test_batch_run_toml_writer_is_a_direct_lfx_dependency() -> None:
    """Batch Run is built in, so its TOML writer must be present in bare LFX."""
    pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"
    pyproject = tomli.loads(pyproject_path.read_text(encoding="utf-8"))
    requirements = [Requirement(value) for value in pyproject["project"]["dependencies"]]

    assert any(requirement.name == "toml" for requirement in requirements)
