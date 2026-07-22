"""Regression tests for release workflow package-version boundaries."""

from __future__ import annotations

from pathlib import Path

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"
NIGHTLY_BUILD_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "nightly_build.yml"
NIGHTLY_RELEASE_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release_nightly.yml"
CROSS_PLATFORM_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "cross-platform-test.yml"


def _job_block(start_job: str, end_job: str) -> str:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
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


def test_nightly_coordinates_core_from_tag_commit_through_publish() -> None:
    nightly_build = NIGHTLY_BUILD_PATH.read_text(encoding="utf-8")
    nightly_release = NIGHTLY_RELEASE_PATH.read_text(encoding="utf-8")
    cross_platform = CROSS_PLATFORM_PATH.read_text(encoding="utf-8")

    assert "src/langflow-core/pyproject.toml" in nightly_build
    assert "build-nightly-core:" in nightly_release
    assert "dist-nightly-core" in nightly_release
    assert "publish-nightly-core:" in nightly_release
    assert 'core-artifact-name: "dist-nightly-core"' in nightly_release
    assert "needs: [build-nightly-main, test-cross-platform, publish-nightly-core" in nightly_release
    assert "core-artifact-name:" in cross_platform
    assert "./core-dist" in cross_platform


if __name__ == "__main__":
    test_finalized_bundles_do_not_influence_shared_rc_number()
    test_bundle_build_only_restamps_unpublished_versions()
    test_nightly_coordinates_core_from_tag_commit_through_publish()
    print("All release workflow tests passed.")
