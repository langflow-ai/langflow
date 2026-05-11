"""Regression test for #12228.

When langflow-ide logs through litellm (e.g. to langfuse), litellm imports
its proxy server module, which in turn needs `apscheduler` and `cryptography`
at runtime. These are normally shipped via `litellm[proxy]`, but that extra
pins `boto3` in a way that conflicts with our `aioboto3` transitives. We
therefore add the specific modules directly to the `litellm` optional
dependency group — this test guards against them being dropped.
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REQUIRED_PACKAGES = ("apscheduler", "cryptography")


def _load_base_pyproject() -> dict:
    pyproject_path = Path(__file__).resolve().parents[2] / "base" / "pyproject.toml"
    assert pyproject_path.is_file(), f"pyproject.toml not found at {pyproject_path}"
    with pyproject_path.open("rb") as f:
        return tomllib.load(f)


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
