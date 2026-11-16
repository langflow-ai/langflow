"""Every supported PR and artifact publication must retain compatibility evidence."""

import ast
import os
import subprocess
import sys
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
        "test_source_connection.py",
        "test_source_trust.py",
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


def test_runtime_cases_run_in_required_gate_without_lightweight_job_dependencies():
    required = workflow(".github/workflows/component-compatibility.yml")["jobs"]["compatibility"]
    commands = "\n".join(step.get("run", "") for step in required["steps"])
    assert "component_runtime" not in commands
    assert "--ignore" not in commands
    assert '--health-cmd "pg_isready -U compatibility"' in required["services"]["postgres"]["options"]
    lightweight = workflow(".github/workflows/ci-scripts-test.yml")
    tests = lightweight["jobs"]["test"]["steps"]
    command = next(step["run"] for step in tests if step.get("name") == "Run CI script tests")
    assert "-m 'not component_runtime'" in command
    expected = {
        "test_component_compatibility.py": {
            "test_equal_code_still_detects_every_breaking_contract",
            "test_new_optional_fields_are_compatible",
            "test_new_required_field_without_default_is_breaking",
            "test_renamed_component_can_resolve_through_shared_aliases",
            "test_acknowledged_changes_are_rendered_into_release_notes",
            "test_invalid_acknowledgments_cannot_allow_a_break",
            "test_provider_identity_and_saved_field_removal_use_the_shared_rule",
        },
        "test_component_registry_snapshot.py": {"test_provider_projection_uses_only_production_language_model_fields"},
        "test_component_release_plan.py": {
            "test_runner_preserves_venv_python_and_retains_other_breaks_after_failed_baseline",
            "test_runner_keeps_historical_acknowledgments_after_publication",
        },
    }
    for filename, names in expected.items():
        module = ast.parse((ROOT / "scripts/ci" / filename).read_text())
        marked = {
            node.name
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and any(ast.unparse(mark) == "pytest.mark.component_runtime" for mark in node.decorator_list)
        }
        assert marked == names
        assert filename in commands


def test_plan_receives_lowercase_sha_for_uppercase_release_input(tmp_path):
    job = workflow(".github/workflows/component-compatibility.yml")["jobs"]["compatibility"]
    command = next(step["run"] for step in job["steps"] if step.get("id") == "plan")
    captured = tmp_path / "arguments.txt"
    script = 'uv() { printf "%s\\n" "$@" > "$TASK_ARGUMENTS"; }\n' + command
    commit = "ABCDEF01" * 5
    result = subprocess.run(  # noqa: S603
        ["/bin/bash", "-c", script],
        env={**os.environ, "BASE_SHA": commit, "TASK_ARGUMENTS": str(captured)},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    arguments = captured.read_text().splitlines()
    assert arguments[arguments.index("--base-sha") + 1] == commit.lower()


def test_policy_step_imports_sibling_scripts_from_the_checkout_root():
    job = workflow(".github/workflows/component-compatibility.yml")["jobs"]["compatibility"]
    step = next(step for step in job["steps"] if step.get("name") == "Test comparison policy and failure handling")
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import component_compatibility, component_release_plan, component_registry_snapshot, "
            "historical_compatibility_gate",
        ],
        cwd=ROOT,
        env={**os.environ, **step.get("env", {})},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_saved_flow_preservation_uses_the_existing_full_install_opt_in():
    job = workflow(".github/workflows/component-compatibility.yml")["jobs"]["compatibility"]
    step = next(
        step for step in job["steps"] if step.get("name") == "Preserve the shared rule and difficult saved flows"
    )
    assert step.get("env", {}).get("LFX_TEST_ALLOW_LANGFLOW") == "1"
    assert "LFX_TEST_ALLOW_LANGFLOW" not in job["env"]
    assert "--noconftest" not in step["run"]


def test_lfx_lane_enforces_the_exact_historical_ledger():
    job = workflow(".github/workflows/python_test.yml")["jobs"]["lfx-tests"]
    tests = next(step for step in job["steps"] if step.get("name") == "Run lfx tests")
    assert tests["run"] == (
        'make lfx_tests args="--deselect=tests/unit/upgrade/test_component_compat.py::test_source_release_statuses"'
    )
    gate = next(step for step in job["steps"] if step.get("name") == "Enforce exact historical LFX pins")
    assert gate["run"] == (
        "uv run --project src/lfx --no-sync python scripts/ci/historical_compatibility_gate.py "
        "--ledger scripts/ci/historical_compatibility_limitations.json --output src/lfx/historical-pins.json"
    )
    evidence = next(step for step in job["steps"] if step.get("name") == "Retain historical LFX evidence")
    assert evidence["if"] == "always()"
    assert evidence["with"]["path"] == "src/lfx/historical-pins.json"
