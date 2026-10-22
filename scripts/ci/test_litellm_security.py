"""Prevent isolated installs from bypassing the LiteLLM incident safeguards."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import tomllib
import yaml
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[2]
CONSTRAINT = ROOT / "scripts/ci/security-constraints.txt"
WORKFLOWS = (
    "cross-bundle-test.yml",
    "cross-platform-test.yml",
    "python_test.yml",
    "release-inventory-gate.yml",
    "release.yml",
    "release_bundles.yml",
    "release_nightly.yml",
)


@pytest.mark.parametrize(
    "manifest",
    ["src/backend/base/pyproject.toml", "src/bundles/toolguard/pyproject.toml"],
)
def test_standalone_consumers_exclude_compromised_release(manifest: str) -> None:
    project = tomllib.loads((ROOT / manifest).read_text())["project"]
    guards = [Requirement(value) for value in project["dependencies"] if Requirement(value).name == "litellm"]
    assert len(guards) == 1
    guard = guards[0]
    assert guard.marker is None, "Standalone installs must be protected without extras or workspace constraints"
    assert "1.103.2" in guard.specifier
    assert "1.107.0" not in guard.specifier
    assert "1.103.0" not in guard.specifier


def test_cuga_extras_exclude_compromised_release() -> None:
    for manifest in ("src/backend/base/pyproject.toml", "src/bundles/lfx-bundles/pyproject.toml"):
        project = tomllib.loads((ROOT / manifest).read_text())["project"]
        guards = [
            Requirement(value)
            for value in project["optional-dependencies"]["cuga"]
            if Requirement(value).name == "litellm"
        ]
        assert guards
        for guard in guards:
            assert "1.103.2" in guard.specifier
            assert "1.107.0" not in guard.specifier


def test_ci_constraint_matches_reviewed_lock_without_dropping_upstream_caps() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    versions = {package["version"] for package in lock["package"] if package["name"] == "litellm"}
    constraints = [
        Requirement(line) for line in CONSTRAINT.read_text().splitlines() if line and not line.startswith("#")
    ]
    assert versions == {"1.103.2"}
    assert [str(requirement) for requirement in constraints] == ["litellm==1.103.2"]
    settings = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]
    assert not any(Requirement(value).name == "litellm" for value in settings["override-dependencies"])
    guard = next(
        Requirement(value) for value in settings["constraint-dependencies"] if Requirement(value).name == "litellm"
    )
    assert "1.107.0" not in guard.specifier


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_isolated_ci_installs_inherit_constraints_and_fresh_cache(workflow: str) -> None:
    document = yaml.safe_load((ROOT / ".github/workflows" / workflow).read_text())
    expected = "${{ github.workspace }}/scripts/ci/security-constraints.txt"
    assert document["env"]["UV_CONSTRAINT"] == expected
    assert document["env"]["PIP_CONSTRAINT"] == expected
    for job in document["jobs"].values():
        env = {**document["env"], **job.get("env", {})}
        assert env["UV_CONSTRAINT"] == env["PIP_CONSTRAINT"]
        assert env["UV_CONSTRAINT"].endswith("/scripts/ci/security-constraints.txt")
        available_constraints = set()
        for step in job.get("steps", []):
            assert not {"UV_CONSTRAINT", "PIP_CONSTRAINT"} & step.get("env", {}).keys()
            if step.get("uses", "").startswith("actions/checkout@"):
                options = step.get("with", {})
                sparse = options.get("sparse-checkout")
                if sparse is None or "scripts/ci/security-constraints.txt" in sparse.splitlines():
                    checkout = options.get("path", "").strip("/")
                    relative = "/".join(filter(None, [checkout, "scripts/ci/security-constraints.txt"]))
                    available_constraints.add("${{ github.workspace }}/" + relative)
            if "pip install" in step.get("run", ""):
                assert env["UV_CONSTRAINT"] in available_constraints, "Install constraint must be checked out first"
            if not step.get("uses", "").startswith("astral-sh/setup-uv@"):
                continue
            options = step.get("with", {})
            if options.get("enable-cache") is False:
                continue
            assert options["cache-suffix"] == "litellm-20261022"
            if "cache-dependency-glob" in options:
                assert "scripts/ci/security-constraints.txt" in options["cache-dependency-glob"]


@pytest.fixture
def offline_resolver(tmp_path: Path):
    """Use metadata-only synthetic wheels; never fetch or execute the malicious artifact."""
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv is needed for the offline resolver regression (installed by CI)")
    for name, version, requirements in (
        ("litellm", "1.103.2", []),
        ("litellm", "1.107.0", []),
        ("consumer", "1.0.0", ["litellm>=1.103.1"]),
    ):
        dist_info = f"{name}-{version}.dist-info"
        metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
        metadata += "".join(f"Requires-Dist: {requirement}\n" for requirement in requirements)
        with zipfile.ZipFile(tmp_path / f"{name}-{version}-py3-none-any.whl", "w") as wheel:
            wheel.writestr(f"{dist_info}/METADATA", metadata)
            wheel.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
            wheel.writestr(f"{dist_info}/RECORD", "")
    requirements_path = tmp_path / "requirements.in"
    requirements_path.write_text("consumer\n")

    def resolve(*, constrained: bool, requirement: str = "consumer") -> subprocess.CompletedProcess[str]:
        requirements_path.write_text(f"{requirement}\n")
        env = {key: value for key, value in os.environ.items() if not key.startswith(("UV_", "PIP_"))}
        if constrained:
            env["UV_CONSTRAINT"] = str(CONSTRAINT)
        return subprocess.run(  # noqa: S603
            [
                uv,
                "pip",
                "compile",
                "--offline",
                "--no-index",
                "--no-config",
                "--no-cache",
                "--python",
                sys.executable,
                "--find-links",
                str(tmp_path),
                str(requirements_path),
            ],
            cwd=tmp_path,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    return resolve


def test_constraint_protects_transitive_install_without_workspace_lock(offline_resolver) -> None:
    unprotected = offline_resolver(constrained=False)
    assert unprotected.returncode == 0, unprotected.stderr
    assert "litellm==1.107.0" in unprotected.stdout
    protected = offline_resolver(constrained=True)
    assert protected.returncode == 0, protected.stderr
    assert "litellm==1.103.2" in protected.stdout
    assert "litellm==1.107.0" not in protected.stdout


def test_constraint_fails_closed_for_incompatible_requirement(offline_resolver) -> None:
    result = offline_resolver(constrained=True, requirement="litellm==1.107.0")
    assert result.returncode != 0
    assert "No solution found" in result.stderr
