"""Trusted synthetic fixture generator, used only by helper qualification CI."""

import json
import sqlite3
from pathlib import Path

import chromadb

root = Path("/fixture")
client = chromadb.PersistentClient(path=str(root / "source"))
expected = {}
for metric in ("l2", "cosine", "ip"):
    collection = client.create_collection(
        f"fixture-{metric}",
        embedding_function=None,
        configuration={"hnsw": {"space": metric, "batch_size": 10, "sync_threshold": 10}},
    )
    ids = [f"doc-{index}" for index in range(240)]
    collection.add(
        ids=ids,
        documents=[f"Document {index}" for index in range(240)],
        metadatas=[
            {
                "job_id": "job-1",
                "source_metadata": '{"region":"West","labels":["a","b"]}',
                "ordinal": index,
                "active": bool(index % 2),
            }
            for index in range(240)
        ],
        embeddings=[[float(index), 1.0, 2.0, 3.0] for index in range(240)],
    )
    collection.delete(ids=["doc-5", "doc-9"])
    collection.update(ids=["doc-2"], documents=["Updated document"], embeddings=[[0.5, 1.0, 2.0, 3.0]])
    collection.add(
        ids=["pending-doc"],
        documents=["Pending document"],
        metadatas=[{"pending": True}],
        embeddings=[[1.0, 2.0, 3.0, 4.0]],
    )
    data = collection.get(include=["documents", "metadatas", "embeddings"])
    expected[metric] = {
        native_id: {
            "content": data["documents"][index],
            "metadata": data["metadatas"][index],
            "embedding": data["embeddings"][index].tolist(),
        }
        for index, native_id in enumerate(data["ids"])
    }
empty = client.create_collection("fixture-empty", embedding_function=None)
empty.add(ids=["dimension-probe"], embeddings=[[1.0, 2.0, 3.0, 4.0]], documents=["Deleted dimension probe"])
empty.delete(ids=["dimension-probe"])
(root / "expected.json").write_text(json.dumps(expected), encoding="utf-8")

# Persist a dangerous Python embedding-function configuration without ever
# instantiating it. The fixed native reader must export these existing vectors
# successfully while Python Chroma imports and networking are unavailable.
client._system.stop()  # noqa: SLF001 -- release the synthetic native store before editing stored configuration
with sqlite3.connect(root / "source" / "chroma.sqlite3") as connection:
    config_text = connection.execute(
        "SELECT config_json_str FROM collections WHERE name = ?", ("fixture-l2",)
    ).fetchone()[0]
    config = json.loads(config_text)
    config["embedding_function"] = {
        "type": "known",
        "name": "sentence_transformer",
        "config": {
            "model_name": "https://invalid.example/never-load-this-model",
            "device": "cpu",
            "normalize_embeddings": False,
            "kwargs": {"trust_remote_code": True},
        },
    }
    connection.execute(
        "UPDATE collections SET config_json_str = ?, schema_str = NULL WHERE name = ?",
        (json.dumps(config), "fixture-l2"),
    )
