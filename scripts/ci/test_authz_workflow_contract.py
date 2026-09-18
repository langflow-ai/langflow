"""Structural guardrails for the mandatory registered-authorization CI path."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _workflow(name: str) -> dict:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    # YAML 1.1 treats the unquoted GitHub Actions key `on` as a boolean.
    workflow["on"] = workflow.pop(True)
    return workflow


def test_ci_requires_both_team_sharing_jobs_when_selected():
    workflow = _workflow("ci.yml")
    triggers = workflow["on"]
    for trigger in ("workflow_call", "workflow_dispatch"):
        inputs = triggers[trigger]["inputs"]
        assert {"ref", "base-ref", "frontend-tests-folder", "run-all-tests", "docker-runs-on"} <= set(inputs)

    jobs = workflow["jobs"]
    backend = jobs["test-authz-backend"]
    browser = jobs["test-authz-e2e"]
    assert backend["name"] == "Run Team Sharing Backend Tests"
    assert browser["name"] == "Run Team Sharing E2E"
    assert "authz-sharing" in backend["if"]
    assert "run-all-tests" in backend["if"]
    assert "authz-sharing" in browser["if"]
    assert "run-all-tests" in browser["if"]
    assert backend.get("continue-on-error") is None
    assert browser.get("continue-on-error") is None
    assert backend["strategy"]["matrix"] == {
        "python-version": ["3.10", "3.14"],
        "database": ["sqlite", "postgresql"],
    }
    assert backend["services"]["postgres"]["image"] == "postgres:16"

    browser_inputs = browser["with"]
    assert browser_inputs["authz-mode"] is True
    assert browser_inputs["tests_folder"] == "tests/core/features/authz"
    assert set(yaml.safe_load(browser_inputs["suites"])) == {"api", "database", "workspace"}

    success = jobs["ci_success"]
    assert {"test-authz-backend", "test-authz-e2e"} <= set(success["needs"])
    exit_contract = success["env"]["EXIT_CODE"]
    assert "needs.test-authz-backend.result != 'success'" in exit_contract
    assert "needs.test-authz-e2e.result != 'success'" in exit_contract


def test_full_validation_includes_candidate_docker_job_and_ref():
    workflow = _workflow("ci.yml")
    docker = workflow["jobs"]["test-docker"]
    assert "run-all-tests" in docker["if"]
    assert docker["with"]["ref"] == "${{ inputs.ref || github.ref }}"
    assert "docker-runs-on" in docker["with"]["runs-on"]


def test_authz_jobs_install_the_locked_optional_backend_dependency():
    backend = _workflow("ci.yml")["jobs"]["test-authz-backend"]
    installation = next(
        step for step in backend["steps"] if step.get("name") == "Install credential-free backend test dependencies"
    )["run"]
    assert "--locked" in installation
    assert "--package langflow --package langflow-base" in installation
    assert "--extra authorization" in installation
    assert "--extra postgresql" in installation
    assert "sqlite3.sqlite_version" in installation
    assert "sys.version.split()[0]" in installation
    execution = next(
        step
        for step in backend["steps"]
        if step.get("name", "").endswith("migration, transaction, lifecycle, and API tests")
    )["run"]
    assert "uv run --no-sync pytest" in execution
    assert "src/backend/tests/unit/services/authorization/casbin_spec" in execution

    browser = _workflow("typescript_test.yml")["jobs"]["setup-and-test"]
    installation = next(step for step in browser["steps"] if step.get("name") == "Install Python Dependencies")["run"]
    assert '"$LANGFLOW_E2E_AUTHZ" == "true"' in installation
    assert "--locked" in installation
    assert "--package langflow --package langflow-base" in installation
    assert "--extra authorization" in installation
    assert "--extra audio" in installation
    assert "sqlite3.sqlite_version" in installation
    assert "sys.version.split()[0]" in installation

    unit_job = _workflow("python_test.yml")["jobs"]["build"]
    installation = next(step for step in unit_job["steps"] if step.get("name") == "Install the project")["run"]
    assert "--locked" in installation
    assert "--package langflow --package langflow-base" in installation
    assert "--extra authorization" in installation
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target, following in (("unit_tests", "unit_tests_looponfail"), ("real_services_tests", "lfx_tests")):
        commands = makefile.split(f"{target}: ", 1)[1].split(f"\n{following}:", 1)[0]
        assert "uv sync --frozen --package langflow --package langflow-base --extra authorization" in commands
        assert "uv run --no-sync pytest" in commands
    integration = _workflow("python_test.yml")["jobs"]["integration-tests"]
    assert next(step for step in integration["steps"] if step.get("name") == "Install the project")["run"] == "uv sync"


def test_authz_browser_mode_is_exact_serial_and_collision_free():
    workflow = _workflow("typescript_test.yml")
    triggers = workflow["on"]
    for trigger in ("workflow_call", "workflow_dispatch"):
        assert triggers[trigger]["inputs"]["authz-mode"]["type"] == "boolean"

    assert workflow["env"]["LANGFLOW_E2E_AUTHZ"] == "${{ inputs['authz-mode'] && 'true' || 'false' }}"
    jobs = workflow["jobs"]
    discovery = next(step for step in jobs["determine-test-suite"]["steps"] if step.get("id") == "setup-matrix")
    discovery_script = discovery["run"]
    assert 'TEST_COUNT" != "8' in discovery_script
    assert "inspectAuthzJourneyTitles" in discovery_script
    assert "SHARD_COUNT=1" in discovery_script

    execution = next(
        step for step in jobs["setup-and-test"]["steps"] if step.get("name") == "Execute Playwright Tests"
    )["run"]
    assert "WORKERS=1" in execution
    assert "RETRIES=0" in execution
    assert '--retries="$RETRIES"' in execution
    assert jobs["setup-and-test"]["continue-on-error"].startswith("${{ !inputs['authz-mode']")
    assert jobs["report-gate"]["continue-on-error"].startswith("${{ !inputs['authz-mode']")
    report_validation = next(step for step in jobs["report-gate"]["steps"] if step.get("id") == "validate")["run"]
    assert 'node tests/utils/resolve-blob-reports.mjs "$raw_dir" "$EXPECTED_REPORTS"' in report_validation

    rendered = (ROOT / ".github" / "workflows" / "typescript_test.yml").read_text(encoding="utf-8")
    artifact_prefixes = (
        "blob-report-",
        "playwright-coverage-",
        "playwright-server-log-",
        "html-report-",
        "json-report-",
    )
    for artifact_prefix in artifact_prefixes:
        assert f"{artifact_prefix}${{{{ env.PLAYWRIGHT_ARTIFACT_NAMESPACE }}}}" in rendered


def test_authz_journey_inventory_has_all_exact_ids_once_without_skips():
    spec = (
        ROOT / "src" / "frontend" / "tests" / "core" / "features" / "authz" / "authz-team-sharing.spec.ts"
    ).read_text(encoding="utf-8")
    ids = re.findall(r"\[AUTHZ-JOURNEY-(\d{2})\]", spec)
    assert ids == [f"{index:02d}" for index in range(1, 9)]
    assert spec.count('tag: ["@authz", "@api", "@database", "@workspace", "@release"]') == 8
    assert "test.skip" not in spec
    assert "describe.skip" not in spec


def test_jest_report_validation_remains_blocking_for_read_only_events():
    job = _workflow("jest_test.yml")["jobs"]["jest-unit-tests"]
    steps = job["steps"]
    execution = next(step for step in steps if step["name"] == "Run Frontend Unit Tests")
    assert "if" not in execution
    validation = next(step for step in steps if step["name"] == "Publish Jest Test Results")
    assert validation["if"] == "always()"
    assert validation.get("continue-on-error") is None
    inputs = validation["with"]
    for gate in ("fail_on_failure", "fail_on_parse_error", "require_tests", "require_passed_tests"):
        assert inputs[gate] is True
    assert "head.repo.full_name != github.repository" in inputs["annotate_only"]
    assert "dependabot[bot]" in inputs["annotate_only"]
    comment = next(step for step in steps if step["name"] == "Add Jest Coverage PR Comment")
    assert "head.repo.full_name == github.repository" in comment["if"]
    assert "github.actor != 'dependabot[bot]'" in comment["if"]
    artifact = next(step for step in steps if step["name"] == "Upload Jest Test Results")
    assert artifact["if"] == "always()"
    assert artifact["with"]["if-no-files-found"] == "error"


def test_authz_path_filter_covers_every_contract_layer():
    filters = yaml.safe_load((ROOT / ".github" / "changes-filter.yaml").read_text(encoding="utf-8"))
    paths = set(filters["authz-sharing"])
    assert {
        "Makefile",
        ".github/workflows/python_test.yml",
        "src/frontend/tests/fixtures/prepare-authz-server.mjs",
    } <= set(_workflow("ci-scripts-test.yml")["on"]["pull_request"]["paths"])
    assert {
        "auth_share_implementation_plan*.md",
        "src/backend/base/langflow/services/authorization/**",
        "src/backend/base/langflow/services/database/lock_retry.py",
        "src/backend/base/langflow/services/database/models/deployment/crud.py",
        "src/backend/base/langflow/services/database/models/file/crud.py",
        "src/backend/base/langflow/services/flow/flow_runner.py",
        "src/backend/base/langflow/services/memory_base/service.py",
        "src/backend/base/langflow/services/utils.py",
        "src/backend/base/langflow/services/variable/service.py",
        "src/backend/base/langflow/alembic/**",
        "src/backend/base/langflow/agentic/utils/assistant_runner.py",
        "src/backend/base/langflow/initial_setup/setup.py",
        "src/backend/base/langflow/api/v1/mappers/deployments/helpers.py",
        "src/backend/base/langflow/api/v1/mappers/deployments/sync.py",
        "src/backend/base/langflow/api/v1/memories.py",
        "src/backend/base/langflow/api/v1/models.py",
        "src/backend/base/langflow/api/v1/variable.py",
        "src/backend/base/langflow/api/v1/projects_mcp_helpers.py",
        "src/backend/base/langflow/api/v2/files.py",
        "src/lfx/src/lfx/services/authorization/**",
        "src/lfx/src/lfx/services/deps.py",
        "src/lfx/src/lfx/services/manager.py",
        "src/lfx/tests/unit/services/test_service_manager.py",
        "src/backend/tests/conftest.py",
        "src/backend/base/langflow/tests/api/v1/test_deployment_guard_delete_endpoints.py",
        "src/backend/tests/unit/api/test_s3_endpoints.py",
        "src/backend/tests/unit/api/v1/test_deployment_guard_retry.py",
        "src/backend/tests/unit/api/v1/test_deployment_route_handlers.py",
        "src/backend/tests/unit/api/v1/test_deployment_sync.py",
        "src/backend/tests/unit/api/v1/test_projects.py",
        "src/backend/tests/unit/api/v1/test_variable.py",
        "src/backend/tests/unit/api/v2/test_files.py",
        "src/backend/tests/unit/services/auth/test_auth_service.py",
        "src/backend/tests/unit/services/database/test_lock_retry.py",
        "src/backend/tests/unit/utils/test_flow_secrets.py",
        "src/frontend/tests/core/features/authz/**",
        "src/frontend/tests/fixtures/prepare-authz-server.mjs",
        "src/frontend/src/customization/utils/custom-should-skip-auth-refresh.ts",
        "src/frontend/src/customization/components/resource-share-dialog/**",
        "src/frontend/src/stores/flowStore.ts",
        "src/frontend/src/stores/flowsManagerStore.ts",
        "src/frontend/src/controllers/API/__tests__/api-auth-maintenance.test.ts",
        "src/frontend/tests/utils/resolve-blob-reports*",
        "scripts/ci/authz_endpoint_matrix.json",
        ".github/workflows/ci.yml",
        ".env.example",
        "AGENTS.md",
        "Makefile",
    } <= paths
