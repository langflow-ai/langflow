"""Regression tests for release workflow package-version boundaries."""

from __future__ import annotations

from pathlib import Path

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"
NIGHTLY_WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release_nightly.yml"
CROSS_PLATFORM_WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "cross-platform-test.yml"
DB_MIGRATION_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "db-migration-validation.yml"
)
PYTHON_TEST_WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "python_test.yml"


def _job_block(start_job: str, end_job: str) -> str:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    start = workflow.index(f"\n  {start_job}:")
    end = workflow.index(f"\n  {end_job}:", start)
    return workflow[start:end]


def _nightly_job_block(start_job: str, end_job: str) -> str:
    workflow = NIGHTLY_WORKFLOW_PATH.read_text(encoding="utf-8")
    start = workflow.index(f"\n  {start_job}:")
    end = workflow.index(f"\n  {end_job}:", start)
    return workflow[start:end]


def test_finalized_bundles_do_not_influence_shared_rc_number() -> None:
    rc_job = _job_block("determine-rc-number", "determine-base-version")

    assert 'if grep -Fxq "$version" "$output_file"; then' in rc_job
    assert "excluding its historical RCs" in rc_job
    assert 'consider_versions "PyPI ${package_name}"' in rc_job


def test_bundle_build_only_restamps_unpublished_versions() -> None:
    bundle_job = _job_block("build-bundles", "test-cross-platform")

    assert "Set unpublished bundle versions for pre-release" in bundle_job
    assert 'if pypi_final_exists "$PACKAGE_NAME" "$CURRENT_VERSION"; then' in bundle_job
    assert "final version is already published" in bundle_job
    assert "langflow_pre_release_tag.py" in bundle_job
    assert "Relax bundle lfx floor for pre-release" in bundle_job
    assert "bundle-version-manifest.json" in bundle_job


def test_full_release_can_reuse_a_published_core() -> None:
    validation = _job_block("validate-dependencies", "determine-rc-number")
    main_build = _job_block("build-main", "build-bundles")

    assert "Cannot release Langflow Main without releasing Langflow Base" not in validation
    assert "resolve its compatible langflow-core dependency from PyPI" in validation
    assert "Download core artifact" in main_build
    assert "Resolve pre-release core dependency" in main_build
    assert "https://pypi.org/pypi/langflow-core/json" in main_build
    assert "Update langflow-core dependencies for pre-release" in main_build
    assert "Update bundle dependencies for pre-release" in main_build
    assert "update_bundle_prerelease_dependencies.py" in main_build
    assert "bundle-release-dist" in main_build
    assert "pyproject.toml || true" in main_build
    assert "Update langflow-base dependency for pre-release" not in main_build
    assert "path: dist/langflow-*.whl" in main_build
    assert "uv pip install dist/langflow-*.whl" in main_build


def test_publish_order_is_base_then_core_then_full() -> None:
    core_publish = _job_block("publish-core", "publish-bundles")
    main_publish = _job_block("publish-main", "publish-sdk")

    assert "publish-base" in core_publish
    assert "publish-core" in main_publish
    assert "needs.publish-base.result == 'success'" not in main_publish


def test_nightly_builds_and_publishes_core_between_base_and_full() -> None:
    core_build = _nightly_job_block("build-nightly-core", "build-nightly-main")
    core_publish = _nightly_job_block("publish-nightly-core", "publish-nightly-bundles")
    main_publish = _nightly_job_block("publish-nightly-main", "call_docker_build_base")

    assert "dist-nightly-base" in core_build
    assert "dist-nightly-core" in core_build
    assert "publish-nightly-base" in core_publish
    assert "publish-nightly-core" in main_publish


def test_main_only_cross_platform_run_does_not_require_core_only_job() -> None:
    workflow = CROSS_PLATFORM_WORKFLOW_PATH.read_text(encoding="utf-8")
    summary = workflow[workflow.index("\n  test-summary:") :]

    assert "EXPECT_CORE_RUNTIME" in summary
    assert 'if [ "$EXPECT_CORE_RUNTIME" = "true" ]' in summary


def test_nightly_migration_install_requests_core_explicitly() -> None:
    workflow = DB_MIGRATION_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "uv pip uninstall -y langflow langflow-core langflow-base" in workflow
    assert "'langflow-core>=0.0.0.dev0'" in workflow
    assert workflow.count('"langflow-core==$VERSION"') == 2


def test_cli_wheel_gate_checks_published_core() -> None:
    workflow = PYTHON_TEST_WORKFLOW_PATH.read_text(encoding="utf-8")
    cli_job = workflow[workflow.index("\n  test-cli:") :]

    assert "src/langflow-core/pyproject.toml" in cli_job
    assert "https://pypi.org/pypi/langflow-core/json" in cli_job
    assert "ignore-nothing-to-cache: true" in cli_job
    assert 'if [ "$status" = "404" ]' in cli_job
    assert "langflow-base-nightly" not in cli_job


if __name__ == "__main__":
    test_finalized_bundles_do_not_influence_shared_rc_number()
    test_bundle_build_only_restamps_unpublished_versions()
    test_full_release_can_reuse_a_published_core()
    test_publish_order_is_base_then_core_then_full()
    test_nightly_builds_and_publishes_core_between_base_and_full()
    test_main_only_cross_platform_run_does_not_require_core_only_job()
    test_nightly_migration_install_requests_core_explicitly()
    test_cli_wheel_gate_checks_published_core()
    print("All release workflow tests passed.")
