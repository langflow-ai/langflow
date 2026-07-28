"""Unit tests for the Locust performance-suite metrics package."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.locust.langflow_runtime.metrics.arrivals import ArrivalAccountant, PacedArrivalScheduler
from tests.locust.langflow_runtime.metrics.correctness import (
    expect_text_size_at_most,
    expect_webhook_n_accept_n_complete,
)
from tests.locust.langflow_runtime.metrics.registry import (
    TrackedHitlRequest,
    TrackedWebhookCopy,
    TrackedWorkflowJob,
    get_registry,
)
from tests.locust.langflow_runtime.metrics.reports import redact_secrets
from tests.locust.langflow_runtime.metrics.validity import (
    InvalidRunReason,
    MeasurementValidity,
    check_missed_arrival_ratio,
)


def test_registry_ops_do_not_embed_ids_in_metric_names() -> None:
    registry = get_registry()
    registry.clear_all()

    job = TrackedWorkflowJob(
        job_id="job-uuid-123",
        flow_id="flow-uuid-456",
        accepted_at=datetime.now(UTC),
    )
    registry.register_workflow(job)
    registry.update_workflow("job-uuid-123", started_at=datetime.now(UTC), status="running")

    webhook = TrackedWebhookCopy(copy_id="copy-abc", endpoint="perf_webhook_passthrough")
    registry.register_webhook(webhook)
    registry.update_webhook("copy-abc", accepted_count=3, completed_count=1, in_flight=2)

    hitl = TrackedHitlRequest(
        job_id="job-hitl-1",
        request_id="req-hitl-1",
        flow_id="flow-hitl",
        phase="pending",
    )
    registry.register_hitl(hitl)

    workflows = registry.list_workflows()
    assert len(workflows) == 1
    assert workflows[0].job_id == "job-uuid-123"
    assert workflows[0].status == "running"

    outstanding = registry.outstanding_workflows()
    assert len(outstanding) == 1
    assert outstanding[0].job_id == "job-uuid-123"

    outstanding_webhooks = registry.outstanding_webhooks()
    assert len(outstanding_webhooks) == 1
    assert outstanding_webhooks[0].copy_id == "copy-abc"

    residual = registry.residual_hitl()
    assert len(residual) == 1
    assert residual[0].request_id == "req-hitl-1"

    drain = registry.drain_snapshot()
    assert drain["outstanding_workflows"] == ["job-uuid-123"]
    assert drain["outstanding_webhooks"] == ["copy-abc"]
    assert drain["residual_hitl"] == ["req-hitl-1"]

    # Metric/event names must remain static — ids live only in registry values.
    for key in drain:
        assert "job-uuid" not in key
        assert "copy-abc" not in key

    registry.clear_all()
    assert registry.list_workflows() == []
    assert registry.outstanding_webhooks() == []
    assert registry.residual_hitl() == []


def test_arrival_miss_accounting_without_catch_up_replay() -> None:
    accountant = ArrivalAccountant()

    for _ in range(5):
        accountant.record_intended_slot()

    accountant.record_attempt()
    accountant.record_accepted()
    accountant.record_started()
    accountant.record_terminal(success=True)

    for reason in ("backlog", "backlog", "timeout"):
        accountant.record_miss(reason)

    snapshot = accountant.snapshot()
    assert snapshot["intended"] == 5
    assert snapshot["attempted"] == 1
    assert snapshot["missed"] == 3
    assert snapshot["accepted"] == 1
    assert snapshot["started"] == 1
    assert snapshot["terminal"] == 1
    assert snapshot["successful"] == 1
    assert snapshot["miss_reasons"] == {"backlog": 2, "timeout": 1}

    # Missed slots are recorded but not replayed as extra attempts.
    assert snapshot["attempted"] < snapshot["intended"]
    assert snapshot["missed"] + snapshot["attempted"] <= snapshot["intended"]


def test_paced_scheduler_skips_expired_slots_without_catch_up() -> None:
    now = [10.0]
    scheduler = PacedArrivalScheduler(2.0, allowed_lateness_s=0.1, clock=lambda: now[0])

    first = scheduler.reserve()
    assert first.delay_s == 0
    assert first.missed_slots == 0

    now[0] = 10.5
    second = scheduler.reserve()
    assert second.delay_s == 0
    assert second.missed_slots == 0

    now[0] = 12.0
    late = scheduler.reserve()
    assert late.missed_slots == 2
    assert late.delay_s == 0


def test_webhook_n_accept_n_complete_correctness() -> None:
    ok = expect_webhook_n_accept_n_complete(4, 4)
    assert ok.ok is True
    assert ok.reason is None

    bad = expect_webhook_n_accept_n_complete(4, 2)
    assert bad.ok is False
    assert bad.reason == "webhook accepted (4) != completed (2)"


def test_text_size_limit_uses_utf8_bytes_and_includes_boundary() -> None:
    assert expect_text_size_at_most("é", 2).ok is True

    too_large = expect_text_size_at_most("é", 1)
    assert too_large.ok is False
    assert too_large.reason == "text size 2 bytes exceeded limit 1 bytes"


def test_text_size_limit_rejects_negative_limit() -> None:
    with pytest.raises(ValueError, match="max_bytes must be non-negative"):
        expect_text_size_at_most("", -1)


def test_redact_secrets_recursive() -> None:
    payload = {
        "profile": "step-ramp",
        "api_key": "lf-secret-key",  # pragma: allowlist secret
        "nested": {
            "password": "p@ss",  # pragma: allowlist secret
            "authorization": "Bearer token",  # pragma: allowlist secret
            "safe": "visible",
        },
        "items": [{"token": "abc", "value": 1}],  # pragma: allowlist secret
    }
    redacted = redact_secrets(payload)
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["nested"]["password"] == "***REDACTED***"
    assert redacted["nested"]["authorization"] == "***REDACTED***"
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["items"][0]["token"] == "***REDACTED***"
    assert redacted["items"][0]["value"] == 1


def test_validity_invalidate_accumulates_reasons() -> None:
    validity = MeasurementValidity()
    assert validity.is_valid is True
    assert validity.to_dict() == {"valid": True, "reasons": []}

    validity.invalidate(InvalidRunReason.GENERATOR_SATURATED)
    validity.invalidate("custom_reason")
    validity.invalidate(InvalidRunReason.GENERATOR_SATURATED)

    assert validity.is_valid is False
    result = validity.to_dict()
    assert result["valid"] is False
    assert result["reasons"] == [
        InvalidRunReason.GENERATOR_SATURATED,
        "custom_reason",
    ]

    ratio_reason = check_missed_arrival_ratio(missed=3, intended=10, max_ratio=0.1)
    assert ratio_reason == InvalidRunReason.MISSED_ARRIVAL_RATIO
