"""Verify CI wires a real redis:7 service and runs the real-service tier."""

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


def _real_services_job(workflow: dict) -> dict | None:
    return next((j for name, j in workflow["jobs"].items() if "real" in name and "service" in name), None)


@pytest.mark.no_blockbuster
def test_real_services_job_exists(workflow: dict) -> None:
    assert _real_services_job(workflow) is not None, f"no real-service job; jobs: {list(workflow['jobs'])}"


@pytest.mark.no_blockbuster
def test_real_services_job_has_postgres_and_redis_services(workflow: dict) -> None:
    real_services = _real_services_job(workflow)
    assert real_services is not None
    images = {svc["image"] for svc in real_services["services"].values()}
    assert any(img.startswith("postgres:") for img in images), images
    assert any(img.startswith("redis:") for img in images), images


@pytest.mark.no_blockbuster
def test_real_services_job_sets_both_test_uris() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "LANGFLOW_TEST_DATABASE_URI" in text
    assert "LANGFLOW_TEST_REDIS_URL" in text
    assert "-m real_services" in text or "real_services_tests" in text
