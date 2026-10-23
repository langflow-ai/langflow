"""Block compromised LiteLLM releases through normal package requirements."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import tomllib
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = [
    "src/backend/base/pyproject.toml",
    "src/bundles/toolguard/pyproject.toml",
    "src/bundles/lfx-bundles/pyproject.toml",
]


@pytest.fixture(params=MANIFESTS)
def litellm_guard(request: pytest.FixtureRequest) -> Requirement:
    project = tomllib.loads((ROOT / request.param).read_text())["project"]
    dependencies = (
        project["optional-dependencies"]["cuga"] if project["name"] == "lfx-bundles" else project["dependencies"]
    )
    guards = [Requirement(value) for value in dependencies if Requirement(value).name == "litellm"]
    assert guards, "Standalone installs need a published requirement, not just a workspace constraint"
    for guard in guards:
        assert "1.107.0" not in guard.specifier
        assert "1.103.0" not in guard.specifier
        assert "1.103.2" in guard.specifier
        assert "1.106.2" in guard.specifier, "Do not freeze installs to the current lockfile version"
        if project["name"] != "lfx-bundles":
            assert guard.marker is None
    # Exercise CUGA's version restriction independently of its platform markers.
    guard = guards[0]
    guard.marker = None
    return guard


def test_workspace_excludes_compromised_release_without_overriding_upstream_caps() -> None:
    settings = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]
    assert not any(Requirement(value).name == "litellm" for value in settings["override-dependencies"])
    guard = next(
        Requirement(value) for value in settings["constraint-dependencies"] if Requirement(value).name == "litellm"
    )
    assert "1.107.0" not in guard.specifier
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    versions = {package["version"] for package in lock["package"] if package["name"] == "litellm"}
    assert versions
    assert all(version in guard.specifier for version in versions)


@pytest.fixture
def offline_resolver(tmp_path: Path):
    """Resolve harmless metadata-only wheels with pip; never download or execute the malicious artifact."""

    def resolve(guard: Requirement | None, *, force_compromised: bool = False) -> subprocess.CompletedProcess[str]:
        dependencies = ["upstream"] + ([str(guard)] if guard else [])
        for name, version, requirements in (
            ("litellm", "1.103.2", []),
            ("litellm", "1.106.2", []),
            ("litellm", "1.107.0", []),
            ("upstream", "1.0.0", ["litellm>=1.103.1"]),
            ("consumer", "1.0.0", dependencies),
        ):
            dist_info = f"{name}-{version}.dist-info"
            metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
            metadata += "".join(f"Requires-Dist: {requirement}\n" for requirement in requirements)
            with zipfile.ZipFile(tmp_path / f"{name}-{version}-py3-none-any.whl", "w") as wheel:
                wheel.writestr(f"{dist_info}/METADATA", metadata)
                wheel.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
                wheel.writestr(f"{dist_info}/RECORD", "")
        env = {key: value for key, value in os.environ.items() if not key.startswith(("UV_", "PIP_"))}
        env["PIP_CONFIG_FILE"] = os.devnull
        return subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--dry-run",
                "--ignore-installed",
                "--no-index",
                "--no-cache-dir",
                "--disable-pip-version-check",
                "--find-links",
                str(tmp_path),
                "--report",
                str(tmp_path / "resolved.json"),
                "consumer",
                *(["litellm==1.107.0"] if force_compromised else []),
            ],
            cwd=tmp_path,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    return resolve


def test_published_requirement_protects_transitive_install_without_lockfile(
    litellm_guard: Requirement, offline_resolver, tmp_path: Path
) -> None:
    unprotected = offline_resolver(None)
    assert unprotected.returncode == 0, unprotected.stdout + unprotected.stderr
    before = json.loads((tmp_path / "resolved.json").read_text())
    assert any(item["metadata"]["version"] == "1.107.0" for item in before["install"])

    protected = offline_resolver(litellm_guard)
    assert protected.returncode == 0, protected.stdout + protected.stderr
    after = json.loads((tmp_path / "resolved.json").read_text())
    versions = {item["metadata"]["name"]: item["metadata"]["version"] for item in after["install"]}
    assert versions["litellm"] == "1.106.2"


def test_published_requirement_rejects_explicit_compromised_release(
    litellm_guard: Requirement, offline_resolver
) -> None:
    result = offline_resolver(litellm_guard, force_compromised=True)
    assert result.returncode != 0
    assert "ResolutionImpossible" in result.stderr
