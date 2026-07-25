"""Known dataset ids referenced by ``fixture_index`` ``dataset_selector`` values.

Inputs themselves live in Python modules (``kb_corpus``, ``storage_payload``,
``v1_contracts``). This registry is only the allow-list of selector ids,
checked by ``validate_fixtures`` and unit tests.
"""

from __future__ import annotations

from types import MappingProxyType

from tests.locust.langflow_runtime.datasets.kb_corpus import (
    KB_CHUNK_SIZE,
    KB_DOC_BYTES,
    KB_DOC_COUNT,
    materialize_kb_corpus,
)
from tests.locust.langflow_runtime.datasets.storage_payload import STORAGE_PAYLOAD_BYTES, bounded_payload_text
from tests.locust.langflow_runtime.flows.defaults import DEFAULT_KB_QUERY, DEFAULT_PAYLOAD_FILENAME
from tests.locust.langflow_runtime.v1_contracts import DEFAULT_WEBHOOK_PAYLOAD, HITL_LIFECYCLE_STEPS

DATASETS = MappingProxyType(
    {
        "kb/bounded_corpus": {
            "document_count": KB_DOC_COUNT,
            "bytes_per_document": KB_DOC_BYTES,
            "chunk_size": KB_CHUNK_SIZE,
            "known_query": DEFAULT_KB_QUERY,
            "materialize": materialize_kb_corpus,
        },
        "storage/bounded_payload": {
            "bytes": STORAGE_PAYLOAD_BYTES,
            "file_name": DEFAULT_PAYLOAD_FILENAME,
            "render": bounded_payload_text,
        },
        "webhook/default_payload": {
            "payload": DEFAULT_WEBHOOK_PAYLOAD,
        },
        "hitl/approve_decision": {
            "decision": "Approve",
            "expected_lifecycle": HITL_LIFECYCLE_STEPS,
        },
    }
)

DATASET_IDS = frozenset(DATASETS)
