"""Flow ingestion must publish the totals stored in the SQLite knowledge base."""

import pytest
from langchain_core.embeddings import Embeddings
from langflow.services.deps import get_settings_service
from lfx.components.files_and_knowledge.knowledge import KnowledgeComponent
from lfx.schema.dataframe import DataFrame


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


@pytest.mark.parametrize("allow_duplicates", [False, True])
async def test_flow_ingestion_updates_sqlite_totals(
    client, logged_in_headers, active_user, monkeypatch, tmp_path, allow_duplicates
):
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    monkeypatch.setattr(
        "lfx.components.files_and_knowledge.knowledge.get_embeddings", lambda **_kwargs: LocalEmbeddings()
    )
    name = "flow_ingestion_stats"
    endpoint = f"/api/v1/knowledge_bases/{name}"
    response = await client.post(
        "/api/v1/knowledge_bases",
        json={"name": name, "embedding_provider": "OpenAI", "embedding_model": "text-embedding-3-small"},
        headers=logged_in_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["backend_type"] == "sqlite"
    response = await client.get(endpoint, headers=logged_in_headers)
    assert response.json()["chunks"] == 0
    assert response.json()["status"] == "empty"

    texts = ["first document", "second document", "third document", "fourth document", "café document"]
    component = KnowledgeComponent(
        knowledge_base=name,
        column_config=[
            {"column_name": "text", "vectorize": True, "identifier": False},
            {"column_name": "source", "vectorize": False, "identifier": False},
        ],
        allow_duplicates=allow_duplicates,
        _user_id=active_user.id,
    )

    repeated_texts = texts * (2 if allow_duplicates else 1)
    for input_texts, expected_texts in (
        (texts, texts),
        (texts, repeated_texts),
        (["appended document"], [*repeated_texts, "appended document"]),
    ):
        component.set(input_df=DataFrame({"text": input_texts, "source": ["documents.txt"] * len(input_texts)}))
        await component.build_kb_info()
        response = await client.get(f"{endpoint}/chunks", headers=logged_in_headers)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == len(expected_texts)
        assert sorted(chunk["content"] for chunk in response.json()["chunks"]) == sorted(expected_texts)

        response = await client.get(endpoint, headers=logged_in_headers)
        assert response.status_code == 200, response.text
        info = response.json()
        assert info["chunks"] == len(expected_texts)
        assert info["words"] == sum(len(text.split()) for text in expected_texts)
        assert info["characters"] == sum(len(text) for text in expected_texts)
        assert info["size"] > 0
        assert info["source_types"] == ["txt"]
        assert info["status"] == "ready"

    response = await client.get(f"{endpoint}/runs", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    runs = response.json()["runs"]
    assert len(runs) == 3
    assert all(run["status"] == "succeeded" for run in runs)
