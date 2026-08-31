"""Regression tests for coordinated base/full release workflow boundaries."""

from __future__ import annotations

from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"
WORKFLOW_PATH = WORKFLOWS_DIR / "release.yml"
RELEASE_INVENTORY_WORKFLOW_PATH = WORKFLOWS_DIR / "release-inventory-gate.yml"
BUNDLE_WORKFLOW_PATH = WORKFLOWS_DIR / "release_bundles.yml"
NIGHTLY_WORKFLOW_PATH = WORKFLOWS_DIR / "release_nightly.yml"
CROSS_PLATFORM_WORKFLOW_PATH = WORKFLOWS_DIR / "cross-platform-test.yml"
DB_MIGRATION_WORKFLOW_PATH = WORKFLOWS_DIR / "db-migration-validation.yml"
PYTHON_TEST_WORKFLOW_PATH = WORKFLOWS_DIR / "python_test.yml"


def _job_block(path: Path, start_job: str, end_job: str) -> str:
    workflow = path.read_text(encoding="utf-8")
    start = workflow.index(f"\n  {start_job}:")
    end = workflow.index(f"\n  {end_job}:", start)
    return workflow[start:end]


def test_finalized_bundles_do_not_influence_shared_rc_number() -> None:
    rc_job = _job_block(WORKFLOW_PATH, "determine-rc-number", "determine-base-version")

    assert 'if grep -Fxq "$version" "$output_file"; then' in rc_job
    assert "excluding its historical RCs" in rc_job
    assert 'consider_versions "PyPI ${package_name}"' in rc_job
    assert "langflow-core" not in rc_job


def test_bundle_build_uses_one_content_aware_prerelease_plan() -> None:
    bundle_job = _job_block(WORKFLOW_PATH, "build-bundles", "test-cross-platform")

    assert "bundle_release_plan.py restamp" in bundle_job
    assert "--rc-number" in bundle_job
    assert "--lfx-version" in bundle_job
    assert "bundle_release_plan.py artifacts" in bundle_job
    assert "bundle-version-manifest.json" in bundle_job


def test_standalone_bundle_workflow_uses_the_same_release_planner() -> None:
    workflow = BUNDLE_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "bundle_release_plan.py artifacts" in workflow
    assert "bundle_release_plan.py publish" in workflow
    assert "Skipping {name} {version}: already published" not in workflow


def test_full_release_requires_and_consumes_the_aligned_base_artifact() -> None:
    validation = _job_block(WORKFLOW_PATH, "validate-dependencies", "determine-rc-number")
    main_build = _job_block(WORKFLOW_PATH, "build-main", "build-bundles")

    assert "langflow ($main_version) and langflow-base ($base_version) must be version-aligned" in validation
    assert "Please enable 'release_package_base' when releasing Langflow" in validation
    assert "Download base artifact" in main_build
    assert "Update langflow-base dependency for pre-release" in main_build
    assert "update_bundle_prerelease_dependencies.py" in main_build
    assert "path: dist/langflow-*.whl" in main_build
    assert "uv pip install dist/langflow-*.whl" in main_build
    assert "dist-core" not in validation + main_build
    assert "pypi/langflow-core" not in validation + main_build


def test_main_build_prefers_release_wheels_over_workspace_sources() -> None:
    main_build = _job_block(WORKFLOW_PATH, "build-main", "build-bundles")

    assert 'uv pip install --no-sources "${FIND_LINKS[@]}" --prerelease=allow -e .' in main_build


def test_bundle_releases_enter_the_dependency_validation_gate() -> None:
    validation = _job_block(WORKFLOW_PATH, "validate-dependencies", "determine-rc-number")

    assert "inputs.release_bundles" in validation
    assert "persist-credentials: false" in validation


def test_publish_order_is_sdk_lfx_bundles_base_full() -> None:
    sdk = _job_block(WORKFLOW_PATH, "publish-sdk", "publish-lfx")
    lfx = _job_block(WORKFLOW_PATH, "publish-lfx", "call_docker_build_base")
    bundles = _job_block(WORKFLOW_PATH, "publish-bundles", "publish-main")
    base = _job_block(WORKFLOW_PATH, "publish-base", "publish-bundles")
    main = _job_block(WORKFLOW_PATH, "publish-main", "publish-sdk")

    assert "publish-sdk" in lfx
    assert "needs.publish-sdk.result" in lfx
    assert "publish-lfx" in bundles
    assert "needs.publish-lfx.result" in bundles
    assert "publish-bundles" in base
    assert "needs.publish-bundles.result" in base
    assert "publish-base" in main
    assert "needs.publish-base.result" in main
    assert "langflow-core" not in sdk + lfx + bundles + base + main


def test_nightly_publish_order_uses_the_same_dependency_chain() -> None:
    workflow = NIGHTLY_WORKFLOW_PATH.read_text(encoding="utf-8")
    lfx = _job_block(NIGHTLY_WORKFLOW_PATH, "publish-nightly-lfx", "publish-nightly-sdk")
    sdk = _job_block(NIGHTLY_WORKFLOW_PATH, "publish-nightly-sdk", "publish-nightly-base")
    base = _job_block(NIGHTLY_WORKFLOW_PATH, "publish-nightly-base", "publish-nightly-bundles")
    bundles = _job_block(
        NIGHTLY_WORKFLOW_PATH,
        "publish-nightly-bundles",
        "check-nightly-main-pypi-dependencies",
    )
    main = _job_block(NIGHTLY_WORKFLOW_PATH, "publish-nightly-main", "call_docker_build_base")

    assert "publish-nightly-sdk" in lfx
    assert "publish-nightly-lfx" in bundles
    assert "publish-nightly-bundles" in base
    assert "publish-nightly-base" in main
    assert "langflow-core" not in workflow
    assert "build-nightly-core" not in workflow
    assert "publish-nightly-core" not in workflow
    assert "make sdk_publish" in sdk


def test_cross_platform_run_has_a_base_runtime_gate() -> None:
    workflow = CROSS_PLATFORM_WORKFLOW_PATH.read_text(encoding="utf-8")
    summary = workflow[workflow.index("\n  test-summary:") :]

    assert "\n  test-base-runtime:" in workflow
    assert "EXPECT_BASE_RUNTIME" in summary
    assert 'if [ "$EXPECT_BASE_RUNTIME" = "true" ]' in summary
    assert "EXPECT_CORE_RUNTIME" not in workflow


def test_nightly_migration_install_requests_base_explicitly() -> None:
    workflow = DB_MIGRATION_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "'langflow-base>=0.0.0.dev0'" in workflow
    assert workflow.count('"langflow-base==$VERSION"') == 2
    assert "langflow-core" not in workflow


def test_cli_wheel_gate_checks_published_base() -> None:
    workflow = PYTHON_TEST_WORKFLOW_PATH.read_text(encoding="utf-8")
    cli_job = workflow[workflow.index("\n  test-cli:") :]

    assert "src/backend/base/pyproject.toml" in cli_job
    assert "https://pypi.org/pypi/langflow-base/json" in cli_job
    assert "ignore-nothing-to-cache: true" in cli_job
    assert 'if [ "$status" = "404" ]' in cli_job
    assert "langflow-core" not in cli_job


def test_dry_run_accepts_non_tag_refs_and_disables_external_writes() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    validation = _job_block(WORKFLOW_PATH, "validate-tag", "validate-tag-format")

    assert "immutable commit SHA / pull request ref when dry_run is true" in workflow
    assert "Validated dry-run source" in workflow
    assert "RELEASE_REF: ${{ inputs.release_tag }}" in validation
    assert '[[ "$RELEASE_REF" =~ ^[0-9a-fA-F]{40}$ ]]' in validation
    assert '[[ "$RELEASE_REF" =~ ^refs/pull/[0-9]+/(head|merge)$ ]]' in validation
    assert "push_to_registry: ${{ !inputs.dry_run }}" in workflow
    assert workflow.count("if: ${{ !inputs.dry_run }}") >= 5
    assert "!inputs.dry_run &&" in workflow


def test_release_docker_builds_consume_built_wheels() -> None:
    main_docker_job = _job_block(WORKFLOW_PATH, "call_docker_build_main", "call_docker_build_main_backend")
    base_docker_job = _job_block(WORKFLOW_PATH, "call_docker_build_base", "call_docker_build_main")
    docker_workflow = (WORKFLOWS_DIR / "docker-build-v2.yml").read_text(encoding="utf-8")

    assert "build-main" in main_docker_job
    assert "build-bundles" in main_docker_job
    assert "release_artifacts: ${{ needs.build-main.result == 'success' }}" in main_docker_job
    assert "build-base" in base_docker_job
    assert "release_artifacts: ${{ needs.build-base.result == 'success' }}" in base_docker_job
    assert "pattern: dist-*" in docker_workflow
    assert "path: .release-artifacts" in docker_workflow


def test_base_wheel_gate_checks_the_public_langflow_entry_point() -> None:
    lfx_job = _job_block(WORKFLOW_PATH, "build-lfx", "build-base")
    base_job = _job_block(WORKFLOW_PATH, "build-base", "build-main")

    assert "Verify base wheel composition" not in lfx_job
    assert "Verify base wheel composition" in base_job
    assert 'assert "langflow = langflow.langflow_launcher:main" in entry_points' in base_job
    assert 'assert "langflow = langflow.__main__:main" in entry_points' not in base_job
    assert "uv run --no-sync python" in base_job


def test_release_inventory_build_args_use_environment_values() -> None:
    workflow = RELEASE_INVENTORY_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "BASE_VERSION: ${{ inputs.base-version }}" in workflow
    assert "MAIN_VERSION: ${{ inputs.main-version }}" in workflow
    assert '--build-arg "BASE_VERSION=$BASE_VERSION"' in workflow
    assert '--build-arg "MAIN_VERSION=$MAIN_VERSION"' in workflow


def test_expanded_image_reinstalls_release_wheels_after_source_sync() -> None:
    dockerfile = (WORKFLOWS_DIR.parents[1] / "docker" / "build_and_push.Dockerfile").read_text(encoding="utf-8")
    expanded = dockerfile[
        dockerfile.index("FROM full-builder AS full-bundles-builder") : dockerfile.index(
            "################################\n# SHARED RUNTIME"
        )
    ]

    sync_index = expanded.index("uv sync --frozen --extra postgresql --extra bundles")
    release_wheels_index = expanded.index("python3.14 /tmp/install_release_wheels.py")
    pip_check_index = expanded.index("uv pip check")

    assert sync_index < release_wheels_index < pip_check_index
    assert "--mode main" in expanded
    assert "--frontend-source /app/src/backend/base/langflow/frontend" in expanded


def test_docker_builds_share_the_base_constraint_rewrite() -> None:
    repo_root = WORKFLOWS_DIR.parents[1]
    helper = repo_root / "scripts" / "ci" / "rewrite_langflow_base_constraint.sh"
    standard = (repo_root / "docker" / "build_and_push.Dockerfile").read_text(encoding="utf-8")
    enterprise = (repo_root / "docker" / "build_and_push_ep.Dockerfile").read_text(encoding="utf-8")

    assert helper.is_file()
    helper_call = 'sh /tmp/rewrite_langflow_base_constraint.sh "$BASE_VERSION" /app/pyproject.toml'
    assert standard.count(helper_call) == 1
    assert enterprise.count(helper_call) == 1
    assert "base_upper_bound=" not in standard
    assert "base_upper_bound=" not in enterprise


def test_main_wheel_gate_derives_bundle_requirements_from_project_metadata() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    main_gate = workflow[workflow.index("- name: Verify main wheel composition") :]

    assert 'root_metadata["project"]["optional-dependencies"]["bundles"]' in main_gate
    assert "opt_in_standalone" not in main_gate
    assert "bundle_requirement_names == expected_bundle_names" in main_gate
