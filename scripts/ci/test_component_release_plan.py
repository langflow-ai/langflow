"""A release baseline follows each package's own base-branch release line."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from component_release_plan import release_plan


class Index:
    def __init__(self):
        self.calls = []

    def get_versions(self, package):
        self.calls.append(package)
        return {
            "langflow": ("1.12.6", "1.13.3", "1.14.0"),
            "lfx-example": ("0.2.0", "0.4.0", "0.5.0"),
        }[package]


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()  # noqa: S603,S607


def write_project(path: Path, name, version):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n')


def test_application_and_bundle_follow_independent_base_versions(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.test")
    write_project(tmp_path / "pyproject.toml", "langflow", "1.13.3")
    bundle = tmp_path / "src/bundles/example/pyproject.toml"
    write_project(bundle, "lfx-example", "0.4.0")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
    base = git(tmp_path, "rev-parse", "HEAD")
    write_project(tmp_path / "pyproject.toml", "langflow", "1.14.0")
    write_project(bundle, "lfx-example", "0.5.0")
    index = Index()
    result = release_plan(tmp_path, base, index)
    by_name = {entry["distribution"]: entry for entry in result["comparisons"]}
    assert by_name["langflow"]["previous_version"] == "1.13.3"
    assert by_name["lfx-example"]["previous_version"] == "0.4.0"
    assert by_name["langflow"]["target_version"] == "1.14.0"
    assert by_name["lfx-example"]["target_version"] == "0.5.0"
    assert set(index.calls) == {"langflow", "lfx-example"}
    assert json.loads(json.dumps(result)) == result


def test_yanked_versions_are_excluded_by_the_shared_index_client(monkeypatch):
    from bundle_release_plan import PyPIClient

    client = PyPIClient()
    monkeypatch.setattr(
        client, "_get_project", lambda _name: {"releases": {"0.3.0": [{"yanked": True}], "0.2.0": [{"yanked": False}]}}
    )
    assert client.get_versions("lfx-example") == ("0.2.0",)
    from component_release_plan import previous_release

    assert previous_release("0.3.0", client.get_versions("lfx-example")) == "0.2.0"


@pytest.mark.parametrize("invalid", ["path_escape", "omission", "baseline", "target", "scope", "prerelease"])
def test_runner_rejects_forged_or_incomplete_plans_before_installation(tmp_path, invalid):
    from component_compatibility import CompatibilityGateError
    from run_component_compatibility import validate_plan
    from test_component_compatibility import snapshot

    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.test")
    write_project(tmp_path / "pyproject.toml", "langflow", "1.13.3")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
    base = git(tmp_path, "rev-parse", "HEAD")
    write_project(tmp_path / "pyproject.toml", "langflow", "1.14.0")
    plan = release_plan(tmp_path, base, Index())
    row = plan["comparisons"][0]
    if invalid == "path_escape":
        row["distribution"] = "../../outside"
    elif invalid == "omission":
        plan["comparisons"] = []
    elif invalid == "baseline":
        row["baseline_ceiling"] = "1.15.0"
    elif invalid == "target":
        row["target_version"] = "1.15.0"
    elif invalid == "scope":
        row["whole_registry"] = False
    else:
        row["previous_version"] = "1.14.0rc1"
    with pytest.raises(CompatibilityGateError):
        validate_plan(plan, snapshot(package="langflow", version="1.14.0"), tmp_path)
