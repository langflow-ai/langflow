"""Deterministic datasets for the performance suite.

Re-exports KB materialization, storage payload helpers, and the
``DATASET_IDS`` allow-list referenced by ``fixture_index`` selectors.
"""

from tests.locust.langflow_runtime.datasets.kb_corpus import cleanup_kb_corpus, kb_corpus, materialize_kb_corpus
from tests.locust.langflow_runtime.datasets.registry import DATASET_IDS, DATASETS
from tests.locust.langflow_runtime.datasets.storage_payload import bounded_payload_text

__all__ = [
    "DATASETS",
    "DATASET_IDS",
    "bounded_payload_text",
    "cleanup_kb_corpus",
    "kb_corpus",
    "materialize_kb_corpus",
]
