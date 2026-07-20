"""Regression tests for release workflow package-version boundaries."""

from __future__ import annotations

from pathlib import Path

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"
BUNDLE_WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release_bundles.yml"


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


def test_bundle_build_uses_one_content_aware_prerelease_plan() -> None:
    bundle_job = _job_block("build-bundles", "test-cross-platform")

    assert "Apply content-aware bundle pre-release plan" in bundle_job
    assert "bundle_release_plan.py restamp" in bundle_job
    assert "--rc-number" in bundle_job
    assert "--lfx-version" in bundle_job
    assert "bundle-version-plan.json" in bundle_job
    assert "bundle_release_plan.py artifacts" in bundle_job


def test_bundle_publication_precedes_lfx_and_verifies_public_artifacts() -> None:
    bundle_job = _job_block("publish-bundles", "publish-main")
    lfx_job = _job_block("publish-lfx", "call_docker_build_base")

    assert "needs: [build-bundles, test-cross-platform, ci]" in bundle_job
    assert "bundle_release_plan.py publish" in bundle_job
    assert "--verify-attempts 10" in bundle_job
    assert "publish-lfx" not in bundle_job
    assert "publish-bundles" in lfx_job
    assert "needs.publish-bundles.result == 'success'" in lfx_job


def test_standalone_bundle_workflow_uses_the_same_release_planner() -> None:
    workflow = BUNDLE_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "bundle_release_plan.py artifacts" in workflow
    assert "bundle_release_plan.py publish" in workflow
    assert "Skipping {name} {version}: already published" not in workflow


if __name__ == "__main__":
    test_finalized_bundles_do_not_influence_shared_rc_number()
    test_bundle_build_uses_one_content_aware_prerelease_plan()
    test_bundle_publication_precedes_lfx_and_verifies_public_artifacts()
    test_standalone_bundle_workflow_uses_the_same_release_planner()
    print("All release workflow tests passed.")
