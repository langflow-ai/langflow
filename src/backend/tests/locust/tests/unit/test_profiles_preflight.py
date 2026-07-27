"""Unit tests for profile loading and preflight dependency matrix."""

from __future__ import annotations

from tests.locust.langflow_runtime.config.loader import load_profile, validate_all_profiles, validate_profile
from tests.locust.langflow_runtime.preflight.dependencies import check_dependencies
from tests.locust.langflow_runtime.provision.flows import index_by_id, load_fixture_index
from tests.locust.langflow_runtime.users.registry import USER_REGISTRY


def test_all_committed_profiles_validate() -> None:
    results = validate_all_profiles()
    failures = {pid: errs for pid, errs in results.items() if errs}
    assert not failures, failures


def test_queue_uses_paced_closed() -> None:
    queue = load_profile("solos/queue")
    assert queue.workload.workload_model == "paced_closed"
    assert queue.workload.arrival_rate_per_s is not None


def test_protocol_calibration_covers_mcp_workflows_and_webhook() -> None:
    profile = load_profile("solos/protocol_calibration")
    assert profile.stress_categories == ["protocol_calibration"]
    assert "mcp" in profile.protocols
    assert "webhook" in profile.protocols
    assert "workflows_sync" in profile.protocols
    classes = {entry.user_class for entry in profile.workload.user_mix}
    assert "ProtocolCalibrationUser" in classes
    assert "WebhookUser" in classes
    assert "webhook" not in profile.stress_categories


def test_ensemble_suite_composes_solo_users() -> None:
    profile = load_profile("tutti/ensemble_suite")
    classes = [entry.user_class for entry in profile.workload.user_mix]
    assert "EnsembleSuiteUser" not in classes
    assert "ChatDbUser" in classes
    assert "QueueUser" in classes
    for name in classes:
        assert name in USER_REGISTRY


def test_preflight_dependencies_use_profile_selectors() -> None:
    entry = index_by_id(load_fixture_index())["perf_queue_short"]
    state = {
        "api_key": "k",
        "project_id": "p",
        "flows": {"perf_queue_short": {"flow_id": "f1"}},
        "fixture_hashes": {"perf_queue_short": entry["fixture_sha256"]},
    }
    # Must not require perf_passthrough for a queue-only profile.
    results = check_dependencies(
        state,
        ["workflows_background"],
        flow_selectors=["perf_queue_short"],
    )
    assert all(r.ok for r in results), results


def test_preflight_dependencies_fail_when_selector_missing() -> None:
    state = {"api_key": "k", "flows": {}}
    results = check_dependencies(
        state,
        ["workflows_sync"],
        flow_selectors=["MemoryChatbotNoLLM"],
    )
    assert any(not r.ok and r.name == "profile_flows" for r in results)


def test_preflight_dependencies_fail_on_stale_fixture_hash() -> None:
    state = {
        "api_key": "k",
        "flows": {"perf_queue_short": {"flow_id": "f1"}},
        "fixture_hashes": {"perf_queue_short": "stale"},
    }
    results = check_dependencies(state, ["workflows_background"], flow_selectors=["perf_queue_short"])
    assert any(not result.ok and result.name == "fixture_hashes" for result in results)


def test_smoke_profile_ok() -> None:
    assert validate_profile("smoke/all_protocols") == []
