"""Every supported PR and artifact publication must retain compatibility evidence."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow(path):
    data = yaml.safe_load((ROOT / path).read_text())
    data["on"] = data.get("on", data.get(True))
    return data


def test_every_main_release_and_patch_pr_runs_without_path_or_draft_filters():
    data = workflow(".github/workflows/component-compatibility.yml")
    assert data["on"]["pull_request"] is None
    job = data["jobs"]["compatibility"]
    assert "if" not in job
    assert "continue-on-error" not in job
    assert data["permissions"] == {"contents": "read"}
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    for required in [
        "--extra bundles",
        "--package langflow-base",
        "--package lfx",
        "component_release_plan.py",
        "run_component_compatibility.py",
        "historical_compatibility_gate.py",
        "test_reader.py",
        "test_report_integrity.py",
        "test_flow_conflict.py",
        "test_update_rebuilt_node.py",
    ]:
        assert required in commands
    assert "LANGFLOW_TEST_POSTGRES_URL" in job["env"]
    assert job["services"]["postgres"]["image"] == "postgres:16-alpine"


def test_release_publication_requires_gate_and_includes_acknowledged_notes():
    data = workflow(".github/workflows/release.yml")
    gate = data["jobs"]["component-compatibility"]
    assert gate["uses"] == "./.github/workflows/component-compatibility.yml"
    release = data["jobs"]["create_release"]
    assert "component-compatibility" in release["needs"]
    assert "needs.component-compatibility.result == 'success'" in release["if"]
    create = next(step for step in release["steps"] if step.get("name") == "Create Release")
    assert create["with"]["bodyFile"] == "compatibility-evidence/release-notes.md"
    assert create["with"]["generateReleaseNotes"] is True


def test_no_artifact_publication_can_precede_compatibility_checks():
    data = workflow(".github/workflows/release.yml")
    reservation = data["jobs"]["reserve-final-release"]
    assert "component-compatibility" in reservation["needs"]
    assert "needs.component-compatibility.result == 'success'" in reservation["if"]
    for name, job in data["jobs"].items():
        if name.startswith("publish-"):
            assert "reserve-final-release" in job["needs"]
            assert "needs.reserve-final-release.result == 'success'" in job["if"]
