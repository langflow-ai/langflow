"""The optional fastapi-guard middleware on the real Langflow app.

With LANGFLOW_GUARD_ENABLED and LANGFLOW_GUARD_SECURITY_HEADERS on, knowledge
base searches whose text looks like code must still reach the endpoint, the
other query parameters must still be screened, and the security headers must
leave the voice assistant's microphone usable.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from langflow.api.utils import knowledge_base_service
from langflow.services.security import PERMISSIONS_POLICY

pytest.importorskip("guard")

CODE_LIKE_SEARCHES = ["SELECT * FROM users", "How do I use eval()?"]


@pytest.fixture(autouse=True)
def guard_enabled(monkeypatch):
    # Runs before the client fixture: attach_guard reads the environment once,
    # inside create_app().
    monkeypatch.setenv("LANGFLOW_GUARD_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_GUARD_SECURITY_HEADERS", "true")


@pytest.mark.parametrize("search", CODE_LIKE_SEARCHES)
@patch("langflow.api.v1.knowledge_bases.backend_for_record")
async def test_knowledge_base_search_finds_code_like_text(
    mock_create_backend, search, client: AsyncClient, logged_in_headers, active_user
):
    from lfx.base.knowledge_bases.backends.base import IngestedDocument

    await knowledge_base_service.create_record(
        user_id=active_user.id,
        name="KB1",
        model_selection={"name": "model", "provider": "OpenAI"},
        backend_type="sqlite",
        backend_config={},
    )
    documents = [
        IngestedDocument(content=text, metadata={"_id": str(idx)})
        for idx, text in enumerate([*CODE_LIKE_SEARCHES, "plain text"])
    ]

    async def _iter_documents(*, batch_size: int = 1000, include_embeddings: bool = False):  # noqa: ARG001
        yield documents

    backend = MagicMock()
    backend.iter_documents = _iter_documents
    backend.teardown = AsyncMock()
    mock_create_backend.return_value = backend

    response = await client.get(
        "api/v1/knowledge_bases/KB1/chunks", params={"search": search}, headers=logged_in_headers
    )

    assert response.status_code == 200, response.text
    assert [chunk["content"] for chunk in response.json()["chunks"]] == [search]


async def test_other_chunk_filters_are_still_screened(client: AsyncClient, logged_in_headers):
    response = await client.get(
        "api/v1/knowledge_bases/KB1/chunks",
        params={"job_id": "<script>alert(1)</script>"},
        headers=logged_in_headers,
    )

    assert response.status_code == 400, response.text


async def test_security_headers_keep_the_voice_assistant_microphone(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/config", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert response.headers["permissions-policy"] == PERMISSIONS_POLICY
