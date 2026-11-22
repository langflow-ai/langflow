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


@pytest.mark.component_runtime
def test_runner_preserves_venv_python_and_retains_other_breaks_after_failed_baseline(monkeypatch, tmp_path):
    import copy
    import sys

    import run_component_compatibility as runner
    from component_compatibility import CompatibilityGateError
    from test_component_compatibility import component

    packages = ["langflow", "lfx-example", "lfx-vllm"]
    metadata = {package: {"version": "0.3.0"} for package in packages}
    monkeypatch.setattr(runner, "declared_distributions", lambda *_args: metadata)
    current = {
        "format_version": 1,
        "complete": True,
        "distributions": dict.fromkeys(packages, "0.3.0"),
        "all_types": {"test": {"Example": component(), "Other": component()}},
        "component_packages": {"Example": "lfx-example", "Other": "lfx-vllm"},
    }
    previous = copy.deepcopy(current)
    previous["distributions"] = dict.fromkeys(packages, "0.2.0")
    del current["all_types"]["test"]["Example"]["template"]["hidden_input"]
    plan = {
        "format_version": 1,
        "base_sha": "a" * 40,
        "comparisons": [
            {
                "distribution": package,
                "target_version": "0.3.0",
                "baseline_ceiling": "0.3.0",
                "previous_version": "0.2.0",
                "whole_registry": package == "langflow",
            }
            for package in packages
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    acknowledgments = tmp_path / "acknowledgments.json"
    acknowledgments.write_text('{"format_version": 1, "breaks": []}')
    python = tmp_path / "venv/bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    seen = []

    def export(interpreter, _exporter, output, _home):
        if output.name == "current.json":
            assert interpreter == python
            return current
        return previous

    def run(command):
        if command[:3] == ["uv", "pip", "install"]:
            seen.append(command[-1])
            if command[-1].startswith("langflow["):
                raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(runner, "snapshot", export)
    monkeypatch.setattr(runner, "run", run)
    output = tmp_path / "evidence"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--plan",
            str(plan_path),
            "--python",
            str(python),
            "--output-dir",
            str(output),
            "--acknowledgments",
            str(acknowledgments),
        ],
    )
    with pytest.raises(CompatibilityGateError, match=r"could not verify.*langflow"):
        runner.main()
    report = json.loads((output / "comparison.json").read_text())
    assert [row["distribution"] for row in report["could_not_verify"]] == ["langflow"]
    assert [row["component"] for row in report["changes"]] == ["Example"]
    assert len(seen) == 3
    assert "lfx-example" in (output / "candidate-breaks.md").read_text()
    assert not (output / "release-notes.md").exists()


@pytest.mark.component_runtime
def test_runner_keeps_historical_acknowledgments_after_publication(monkeypatch, tmp_path):
    import copy
    import sys
    from types import SimpleNamespace

    import run_component_compatibility as runner
    from component_compatibility import CompatibilityGateError, compare_registries
    from test_component_compatibility import component, snapshot

    package = "lfx-bundles"
    previous = snapshot({"Retired": component(), "Supported": component()}, package=package, version="1.3.5")
    published = copy.deepcopy(previous)
    published["distributions"][package] = "1.3.6"
    published["all_types"]["test"]["Retired"]["retired_in"] = "1.3.6"
    checkout = copy.deepcopy(published)
    [change] = compare_registries(previous, checkout, package)

    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.test")
    write_project(tmp_path / "pyproject.toml", package, "1.3.6")
    git(tmp_path, "add", "pyproject.toml")
    git(tmp_path, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
    base = git(tmp_path, "rev-parse", "HEAD")

    note = tmp_path / "docs/release_notes/compatibility/retired.md"
    note.parent.mkdir(parents=True)
    note.write_text(f"Replace Retired in saved flows.\nBreak identity {change.id}\n")
    acknowledgments = tmp_path / "acknowledgments.json"
    acknowledgments.write_text(
        json.dumps(
            {
                "format_version": 2,
                "breaks": [
                    {
                        "id": change.id,
                        "distribution": package,
                        "source_version": "1.3.5",
                        "target_version": "1.3.6",
                        "reason": "Retire an obsolete component",
                        "release_note": str(note.relative_to(tmp_path)),
                    }
                ],
            }
        )
    )

    plan_path = tmp_path / "plan.json"
    output = tmp_path / "evidence"
    baseline = previous

    def export(_interpreter, _exporter, output_path, _home):
        return checkout if output_path.name == "current.json" else baseline

    monkeypatch.setattr(runner, "__file__", str(tmp_path / "scripts/ci/run_component_compatibility.py"))
    monkeypatch.setattr(runner, "snapshot", export)
    monkeypatch.setattr(runner, "run", lambda _command: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--plan",
            str(plan_path),
            "--output-dir",
            str(output),
            "--acknowledgments",
            str(acknowledgments),
        ],
    )

    plan_path.write_text(json.dumps(release_plan(tmp_path, base, SimpleNamespace(get_versions=lambda _: ("1.3.5",)))))
    assert runner.main() == 0
    assert change.id in (output / "release-notes.md").read_text()

    baseline = published
    index = SimpleNamespace(get_versions=lambda _: ("1.3.5", "1.3.6"))
    plan_path.write_text(json.dumps(release_plan(tmp_path, base, index)))
    assert runner.main() == 0
    assert change.id not in (output / "release-notes.md").read_text()

    checkout["all_types"]["test"]["Supported"]["outputs"] = []
    [new_break] = compare_registries(published, checkout, package)
    with pytest.raises(CompatibilityGateError, match=f"unacknowledged component breaks {new_break.id}"):
        runner.main()
