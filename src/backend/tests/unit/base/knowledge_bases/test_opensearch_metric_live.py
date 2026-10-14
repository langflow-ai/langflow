"""Opt-in checks of the persisted OpenSearch metric against a real index."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from lfx.base.knowledge_bases.backends import create_backend
from lfx.base.knowledge_bases.backends.base import IngestedDocument


@pytest.mark.api_key_required
async def test_existing_index_metric_survives_a_changed_backend_config():
    if os.getenv("LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS") != "1" or not os.getenv("OPENSEARCH_URL"):
        pytest.skip("Set LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1 and OPENSEARCH_URL")
    pytest.importorskip("opensearchpy")
    kb_name = f"kb_metric_{uuid4().hex[:8]}"
    owner = uuid4()
    backend = create_backend(
        "opensearch",
        kb_name=kb_name,
        user_id=owner,
        backend_config={"url_variable": "OPENSEARCH_URL", "space_type": "l2"},
    )
    try:
        await backend.add_embedded_documents([IngestedDocument(id="old", content="old", embedding=[2.0, 0.0])])
        await backend.teardown()
        backend = create_backend(
            "opensearch",
            kb_name=kb_name,
            user_id=owner,
            backend_config={"url_variable": "OPENSEARCH_URL", "space_type": "cosinesimil"},
        )
        assert backend.distance_metric == "cosine"
        assert await backend.get_distance_metric() == "l2"
        await backend.add_embedded_documents([IngestedDocument(id="new", content="new", embedding=[0.0, 2.0])])
        # A later write cannot change the immutable metric of the existing index.
        assert await backend.get_distance_metric() == "l2"
    finally:
        await backend.delete_collection()
        await backend.teardown()
