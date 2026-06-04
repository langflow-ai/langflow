"""Verify CI wires a real redis:7 service and runs the hard-proof tier."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[5]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "migration-validation.yml"


@pytest.fixture
def workflow() -> dict:
    assert _WORKFLOW.exists(), f"workflow not found at {_WORKFLOW}"
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _hard_proof_job(workflow: dict) -> dict | None:
    return next((j for name, j in workflow["jobs"].items() if "hard" in name and "proof" in name), None)


@pytest.mark.no_blockbuster
def test_hard_proof_job_exists(workflow: dict) -> None:
    assert _hard_proof_job(workflow) is not None, f"no hard-proof job; jobs: {list(workflow['jobs'])}"


@pytest.mark.no_blockbuster
def test_hard_proof_job_has_postgres_and_redis_services(workflow: dict) -> None:
    hard_proof = _hard_proof_job(workflow)
    assert hard_proof is not None
    images = {svc["image"] for svc in hard_proof["services"].values()}
    assert any(img.startswith("postgres:") for img in images), images
    assert any(img.startswith("redis:") for img in images), images


@pytest.mark.no_blockbuster
def test_hard_proof_job_sets_both_test_uris() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "LANGFLOW_TEST_DATABASE_URI" in text
    assert "LANGFLOW_TEST_REDIS_URL" in text
    assert "-m hard_proof" in text or "hard_proof_tests" in text
