"""Regression test for #12228.

When langflow-ide logs through litellm (e.g. to langfuse), litellm imports
its proxy server module, which in turn needs `apscheduler` and `cryptography`
at runtime. These are normally shipped via the much larger `litellm[proxy]`
extra. We add the specific modules directly to the `litellm` optional
dependency group, and this test guards against them being dropped.
"""

from __future__ import annotations

import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REQUIRED_PACKAGES = ("apscheduler", "cryptography")
REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_base_pyproject() -> dict:
    pyproject_path = Path(__file__).resolve().parents[2] / "base" / "pyproject.toml"
    assert pyproject_path.is_file(), f"pyproject.toml not found at {pyproject_path}"
    with pyproject_path.open("rb") as f:
        return tomllib.load(f)


def _load_workspace_pyproject() -> dict:
    with (REPO_ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)


def _active_litellm_override(python_version: str) -> Requirement:
    overrides = _load_workspace_pyproject()["tool"]["uv"]["override-dependencies"]
    requirements = [Requirement(spec) for spec in overrides if Requirement(spec).name == "litellm"]
    active = [
        requirement
        for requirement in requirements
        if requirement.marker is None
        or requirement.marker.evaluate(
            environment={"python_version": python_version, "python_full_version": f"{python_version}.0"}
        )
    ]
    assert len(active) == 1
    return active[0]


def _package_name(spec: str) -> str:
    # Strip extras, version specifiers, and markers.
    for sep in ("[", " ", ";", "=", "<", ">", "!", "~"):
        if sep in spec:
            spec = spec.split(sep, 1)[0]
    return spec.strip().lower()


def test_litellm_optional_dependency_includes_runtime_proxy_modules() -> None:
    pyproject = _load_base_pyproject()
    optional = pyproject["project"]["optional-dependencies"]
    assert "litellm" in optional, "Expected `litellm` optional-dependency group in base/pyproject.toml"

    litellm_specs = optional["litellm"]
    names = {_package_name(s) for s in litellm_specs}

    missing = [pkg for pkg in REQUIRED_PACKAGES if pkg not in names]
    assert not missing, (
        f"The `litellm` optional-dependency group is missing required runtime packages: {missing}. "
        f"These are needed when langflow-ide invokes litellm's proxy server module for logging "
        f"(see issue #12228). Current specs: {litellm_specs}"
    )


def test_litellm_dependent_extras_are_available_on_python_314() -> None:
    """LiteLLM and the extras that require it must not retain a Python 3.14 gate."""
    optional = _load_base_pyproject()["project"]["optional-dependencies"]

    litellm = next(Requirement(spec) for spec in optional["litellm"] if Requirement(spec).name == "litellm")
    assert any(spec.operator == ">=" and spec.version == "1.93.0" for spec in litellm.specifier)
    assert litellm.marker is None

    opik = next(Requirement(spec) for spec in optional["opik"] if Requirement(spec).name == "opik")
    assert opik.marker is None

    toolguard = next(Requirement(spec) for spec in optional["toolguard"] if Requirement(spec).name == "lfx")
    assert "toolguard" in toolguard.extras
    assert toolguard.marker is None


def test_litellm_override_preserves_opik_python310_compatibility() -> None:
    python_310 = _active_litellm_override("3.10").specifier
    assert Version("1.96.0") in python_310
    assert Version("1.97.0") not in python_310

    python_314 = _active_litellm_override("3.14").specifier
    assert Version("1.98.0") in python_314
    assert Version("2.0.0") not in python_314
