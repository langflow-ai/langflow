"""User class registry for the V1 performance suite."""

from __future__ import annotations

USER_REGISTRY: dict[str, str] = {
    "ProtocolCalibrationUser": "tests.locust.langflow_runtime.users.protocol_calibration.ProtocolCalibrationUser",
    "ChatDbUser": "tests.locust.langflow_runtime.users.chat_db.ChatDbUser",
    "KbIngestUser": "tests.locust.langflow_runtime.users.kb.KbIngestUser",
    "KbRetrieveUser": "tests.locust.langflow_runtime.users.kb.KbRetrieveUser",
    "CpuGraphUser": "tests.locust.langflow_runtime.users.cpu_graph.CpuGraphUser",
    "MultiprocUser": "tests.locust.langflow_runtime.users.multiproc.MultiprocUser",
    "DiskIoUser": "tests.locust.langflow_runtime.users.disk_io.DiskIoUser",
    "StorageUser": "tests.locust.langflow_runtime.users.storage.StorageUser",
    "QueueUser": "tests.locust.langflow_runtime.users.queue.QueueUser",
    "HitlUser": "tests.locust.langflow_runtime.users.hitl.HitlUser",
    "WebhookUser": "tests.locust.langflow_runtime.users.webhook.WebhookUser",
    "OutboundUser": "tests.locust.langflow_runtime.users.outbound.OutboundUser",
    "McpUser": "tests.locust.langflow_runtime.users.mcp.McpUser",
    "EnsembleSuiteUser": "tests.locust.langflow_runtime.users.ensemble_suite.EnsembleSuiteUser",
    "EnsembleFlowUser": "tests.locust.langflow_runtime.users.ensemble_flow.EnsembleFlowUser",
}
