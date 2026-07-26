"""Paths and deterministic defaults for flow fixture builders.

Shared constants (dirs, default inputs, KB/outbound names) used by
``build_fixtures``, ``builders``, ``fixture_index``, ``validate_fixtures``,
dataset helpers, and ``tests/locust/tests/``.
"""

from __future__ import annotations

from pathlib import Path

from tests.locust.langflow_runtime.contracts import DEFAULT_WEBHOOK_PAYLOAD, HITL_LIFECYCLE_RULE

FLOWS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = FLOWS_DIR / "fixtures"
PACKAGE_ROOT = FLOWS_DIR.parent  # tests/locust/langflow_runtime
COMPONENTS_DIR = PACKAGE_ROOT / "components"
# langflow_runtime -> locust -> tests -> backend -> src -> <repo>
REPO_ROOT = PACKAGE_ROOT.parents[4]
DATA_DIR = REPO_ROOT / "src" / "backend" / "tests" / "data"
STARTERS_1_6_0_REL = "src/lfx/tests/data/starter_projects_1_6_0"
DATA_REL = "src/backend/tests/data"

FIXTURE_INDEX_VERSION = 1

DEFAULT_PASSTHROUGH_INPUT = "perf-passthrough-ping"
DEFAULT_CHAT_INPUT = "perf-chat-turn"
DEFAULT_QUEUE_INPUT = "perf-queue-ping"
DEFAULT_QUEUE_SLEEP_MS = 50
DEFAULT_CPU_DURATION_MS = 25
DEFAULT_CPU_ITERATIONS = 50_000
DEFAULT_MULTIPROC_COUNT = 2
DEFAULT_MULTIPROC_DURATION_MS = 100
DEFAULT_MULTIPROC_WORKING_SET_BYTES = 4 * 1024 * 1024  # 4 MiB
DEFAULT_DISK_IO_SIZE_BYTES = 4 * 1024 * 1024  # 4 MiB
DEFAULT_KB_DOC_PREFIX = "PERF_KB_DOC"
DEFAULT_KB_QUERY = "PERF_KB_QUERY_KNOWN"
# Deterministic KB name provisioners must create/bind before live KB runs.
DEFAULT_KB_NAME = "perf_kb"
DEFAULT_OUTBOUND_PROMPT = "Say exactly: perf-outbound-ok"
DEFAULT_OUTBOUND_SYSTEM = (
    "You are a performance-suite outbound probe. Reply with exactly the user text and nothing else."
)
# Committed selection; live runs still inject api_key (load_from_db / env).
DEFAULT_OUTBOUND_PROVIDER = "OpenAI"
DEFAULT_OUTBOUND_MODEL = "gpt-4o-mini"
DEFAULT_OUTBOUND_API_KEY_VAR = "OPENAI_API_KEY"  # pragma: allowlist secret
DEFAULT_PAYLOAD_FILENAME = "perf_payload_echo"

__all__ = [
    "COMPONENTS_DIR",
    "DATA_DIR",
    "DATA_REL",
    "DEFAULT_CHAT_INPUT",
    "DEFAULT_CPU_DURATION_MS",
    "DEFAULT_CPU_ITERATIONS",
    "DEFAULT_DISK_IO_SIZE_BYTES",
    "DEFAULT_KB_DOC_PREFIX",
    "DEFAULT_KB_NAME",
    "DEFAULT_KB_QUERY",
    "DEFAULT_MULTIPROC_COUNT",
    "DEFAULT_MULTIPROC_DURATION_MS",
    "DEFAULT_MULTIPROC_WORKING_SET_BYTES",
    "DEFAULT_OUTBOUND_API_KEY_VAR",
    "DEFAULT_OUTBOUND_MODEL",
    "DEFAULT_OUTBOUND_PROMPT",
    "DEFAULT_OUTBOUND_PROVIDER",
    "DEFAULT_OUTBOUND_SYSTEM",
    "DEFAULT_PASSTHROUGH_INPUT",
    "DEFAULT_PAYLOAD_FILENAME",
    "DEFAULT_QUEUE_INPUT",
    "DEFAULT_QUEUE_SLEEP_MS",
    "DEFAULT_WEBHOOK_PAYLOAD",
    "FIXTURES_DIR",
    "FIXTURE_INDEX_VERSION",
    "FLOWS_DIR",
    "HITL_LIFECYCLE_RULE",
    "PACKAGE_ROOT",
    "REPO_ROOT",
    "STARTERS_1_6_0_REL",
]
