"""Performance-suite metrics for Locust load tests."""

from tests.locust.langflow_runtime.metrics.analysis import (
    CandidateKneeBracket,
    PlateauSummary,
    StepCurve,
    build_step_curve,
    suggest_candidate_knee_inputs,
)
from tests.locust.langflow_runtime.metrics.arrivals import ArrivalAccountant
from tests.locust.langflow_runtime.metrics.correctness import (
    CorrectnessResult,
    expect_chat_ordering,
    expect_contains,
    expect_disk_io_contract,
    expect_hitl_request_id,
    expect_kb_retrieval,
    expect_multiproc_metrics,
    expect_stream_terminal,
    expect_webhook_n_accept_n_complete,
    expect_workflow_terminal,
)
from tests.locust.langflow_runtime.metrics.lifecycle import LifecycleRecord, fire_lifecycle, lifecycle_timer
from tests.locust.langflow_runtime.metrics.registry import (
    Registry,
    TrackedHitlRequest,
    TrackedMcpCall,
    TrackedWebhookCopy,
    TrackedWorkflowJob,
    get_registry,
)
from tests.locust.langflow_runtime.metrics.reports import (
    RedactedRunReport,
    attach_listeners,
    redact_secrets,
    set_report_context,
    write_report,
)
from tests.locust.langflow_runtime.metrics.validity import (
    InvalidRunReason,
    MeasurementValidity,
    check_generator_saturation,
    check_missed_arrival_ratio,
)

__all__ = [
    "ArrivalAccountant",
    "CandidateKneeBracket",
    "CorrectnessResult",
    "InvalidRunReason",
    "LifecycleRecord",
    "MeasurementValidity",
    "PlateauSummary",
    "RedactedRunReport",
    "Registry",
    "StepCurve",
    "TrackedHitlRequest",
    "TrackedMcpCall",
    "TrackedWebhookCopy",
    "TrackedWorkflowJob",
    "attach_listeners",
    "build_step_curve",
    "check_generator_saturation",
    "check_missed_arrival_ratio",
    "expect_chat_ordering",
    "expect_contains",
    "expect_disk_io_contract",
    "expect_hitl_request_id",
    "expect_kb_retrieval",
    "expect_multiproc_metrics",
    "expect_stream_terminal",
    "expect_webhook_n_accept_n_complete",
    "expect_workflow_terminal",
    "fire_lifecycle",
    "get_registry",
    "lifecycle_timer",
    "redact_secrets",
    "set_report_context",
    "suggest_candidate_knee_inputs",
    "write_report",
]
